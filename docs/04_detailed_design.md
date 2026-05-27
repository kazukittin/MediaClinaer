# 詳細設計書

## 1. 目的

要件定義と基本設計で確定した方針をもとに、初期実装で必要になる保存形式、設定項目、ログ形式、隔離処理の失敗時ロールバック方針を定義する。

この文書の内容は合意済みの詳細設計として扱う。

## 2. SQLiteスキーマ

SQLiteは `<app_folder>\cache\media_clinaer.sqlite3` に保存する。

### 2.1 schema_version

DBスキーマのバージョンを管理する。

```sql
CREATE TABLE schema_version (
    version INTEGER NOT NULL,
    applied_at TEXT NOT NULL
);
```

### 2.2 scan_sessions

1回のスキャン実行単位を保存する。

```sql
CREATE TABLE scan_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    target_paths_json TEXT NOT NULL,
    total_files INTEGER NOT NULL DEFAULT 0,
    scanned_files INTEGER NOT NULL DEFAULT 0,
    cache_used_count INTEGER NOT NULL DEFAULT 0,
    detection_group_count INTEGER NOT NULL DEFAULT 0,
    error_count INTEGER NOT NULL DEFAULT 0
);
```

`status` は `running`、`completed`、`cancelled`、`failed` を使う。

### 2.3 media_files

スキャンで見つけたメディアファイルを保存する。

```sql
CREATE TABLE media_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_session_id INTEGER NOT NULL,
    path TEXT NOT NULL,
    normalized_path TEXT NOT NULL,
    storage_type TEXT NOT NULL,
    media_type TEXT NOT NULL,
    extension TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    modified_at TEXT NOT NULL,
    sha256 TEXT,
    perceptual_hash TEXT,
    blur_score REAL,
    cache_status TEXT NOT NULL,
    scan_error TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (scan_session_id) REFERENCES scan_sessions(id)
);

CREATE INDEX idx_media_files_path ON media_files(normalized_path);
CREATE INDEX idx_media_files_sha256 ON media_files(sha256);
CREATE INDEX idx_media_files_size ON media_files(size_bytes);
```

`cache_status` は `fresh`、`reused`、`stale`、`error` を使う。

### 2.4 analysis_cache

ファイル単位の解析キャッシュを保存する。次回スキャン時に、パス、サイズ、更新日時が一致すれば再利用する。

```sql
CREATE TABLE analysis_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL UNIQUE,
    normalized_path TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    modified_at TEXT NOT NULL,
    media_type TEXT NOT NULL,
    sha256 TEXT,
    perceptual_hash TEXT,
    blur_score REAL,
    last_scanned_at TEXT NOT NULL,
    last_error TEXT
);

CREATE INDEX idx_analysis_cache_key
ON analysis_cache(normalized_path, size_bytes, modified_at);
```

### 2.5 detection_groups

検出された重複・類似・ブレ候補のグループを保存する。

```sql
CREATE TABLE detection_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_session_id INTEGER NOT NULL,
    group_type TEXT NOT NULL,
    confidence REAL NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (scan_session_id) REFERENCES scan_sessions(id)
);

CREATE INDEX idx_detection_groups_session
ON detection_groups(scan_session_id, group_type);
```

`group_type` は `duplicate_image`、`similar_image`、`blurry_image`、`duplicate_video` を使う。

### 2.6 detection_group_items

検出グループとファイルの対応を保存する。

```sql
CREATE TABLE detection_group_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    detection_group_id INTEGER NOT NULL,
    media_file_id INTEGER NOT NULL,
    recommended_action TEXT NOT NULL,
    selected_by_default INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (detection_group_id) REFERENCES detection_groups(id),
    FOREIGN KEY (media_file_id) REFERENCES media_files(id)
);

CREATE INDEX idx_detection_group_items_group
ON detection_group_items(detection_group_id);
```

`recommended_action` は `keep`、`quarantine_candidate`、`review` を使う。

### 2.7 quarantine_records

隔離したファイルと元ファイルの完全パス紐づけを保存する。

```sql
CREATE TABLE quarantine_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    media_file_id INTEGER,
    original_path TEXT NOT NULL,
    original_normalized_path TEXT NOT NULL,
    quarantined_path TEXT NOT NULL,
    original_size_bytes INTEGER NOT NULL,
    original_modified_at TEXT NOT NULL,
    source_storage_type TEXT NOT NULL,
    status TEXT NOT NULL,
    quarantined_at TEXT NOT NULL,
    error_message TEXT,
    FOREIGN KEY (media_file_id) REFERENCES media_files(id)
);

CREATE INDEX idx_quarantine_original_path
ON quarantine_records(original_normalized_path);
```

`status` は `completed`、`copy_failed`、`delete_failed`、`rollback_failed` を使う。

### 2.8 app_events

アプリ内の主要イベントをSQLiteにも保存する。調査用のテキストログとは別に、画面表示や履歴検索で使う。

```sql
CREATE TABLE app_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    level TEXT NOT NULL,
    event_type TEXT NOT NULL,
    message TEXT NOT NULL,
    path TEXT,
    details_json TEXT
);

CREATE INDEX idx_app_events_created_at ON app_events(created_at);
CREATE INDEX idx_app_events_level ON app_events(level);
```

## 3. 設定ファイル項目

設定ファイルは `<app_folder>\config.json` に保存する。

### 3.1 初期設定例

```json
{
  "version": 1,
  "paths": {
    "cache_dir": "cache",
    "logs_dir": "logs",
    "quarantine_dir": "quarantine"
  },
  "scan": {
    "target_paths": [],
    "image_extensions": [".jpg", ".jpeg", ".png", ".webp", ".bmp"],
    "video_extensions": [".mp4", ".mov", ".avi", ".mkv"],
    "include_subdirectories": true,
    "follow_symlinks": false
  },
  "detection": {
    "enable_duplicate_images": true,
    "enable_similar_images": true,
    "enable_blurry_images": true,
    "enable_duplicate_videos": true,
    "similar_image_hash_distance": 8,
    "blur_threshold": 100.0
  },
  "cache": {
    "enabled": true,
    "retention_days": null
  },
  "quarantine": {
    "preserve_relative_path": true,
    "on_name_collision": "append_hash",
    "verify_copy_before_delete": true
  },
  "ui": {
    "theme": "system",
    "last_opened_result_session_id": null
  }
}
```

### 3.2 設定項目の方針

- `retention_days` は `null` を無期限として扱う。
- `paths` はアプリフォルダからの相対パスで保存する。
- 実行時には必ず完全パスへ解決して扱う。
- `follow_symlinks` は初期値 `false` とする。循環参照や想定外のNAS走査を避けるため。
- `preserve_relative_path` は初期値 `true` とする。隔離フォルダ内で元のフォルダ構造を追いやすくするため。

## 4. ログ形式

ログは2系統に分ける。

### 4.1 テキストログ

人間が読む調査用ログとして `<app_folder>\logs\app.log` に出力する。

形式は1行JSONとする。

```json
{"time":"2026-05-27T10:55:00+09:00","level":"INFO","event":"scan_started","message":"Scan started","path":null,"details":{"session_id":1}}
```

主な項目:

| 項目 | 内容 |
| --- | --- |
| time | ISO 8601形式の日時 |
| level | DEBUG, INFO, WARNING, ERROR |
| event | イベント種別 |
| message | 短い説明 |
| path | 関連ファイルパス |
| details | 補足情報 |

### 4.2 SQLiteイベントログ

画面表示や履歴検索用に `app_events` テーブルへも主要イベントを保存する。

### 4.3 主なイベント種別

| event | 内容 |
| --- | --- |
| app_started | アプリ起動 |
| app_folder_not_writable | アプリフォルダ書き込み不可 |
| scan_started | スキャン開始 |
| scan_completed | スキャン完了 |
| scan_cancelled | スキャン中断 |
| file_scan_failed | ファイル読み取り失敗 |
| long_path_skipped | 長いパスによりスキップ |
| cache_reused | キャッシュ再利用 |
| duplicate_detected | 完全重複検出 |
| similar_detected | 類似画像検出 |
| blurry_detected | ブレ画像検出 |
| quarantine_started | 隔離開始 |
| quarantine_completed | 隔離完了 |
| quarantine_copy_failed | 隔離コピー失敗 |
| quarantine_delete_failed | 隔離元削除失敗 |
| quarantine_rollback_failed | ロールバック失敗 |

## 5. 隔離処理の失敗時ロールバック

隔離処理は、ローカルファイルもNASファイルも同じ安全方針で扱う。

### 5.1 基本手順

1. 隔離先の完全パスを生成する。
2. 隔離先フォルダを作成する。
3. 元ファイルを隔離先へコピーする。
4. コピー後のファイルサイズを確認する。
5. 可能ならコピー後のSHA-256を確認する。
6. コピー検証が成功した場合だけ元ファイルを削除する。
7. 成功または失敗を `quarantine_records` とログに保存する。

初期実装では、NASや巨大動画を考慮して、SHA-256検証は設定で有効・無効にできる余地を残す。ただしファイルサイズ確認は必須とする。

### 5.2 失敗パターン別の扱い

| 失敗箇所 | 扱い | 元ファイル | 隔離先ファイル | status |
| --- | --- | --- | --- | --- |
| 隔離先フォルダ作成失敗 | 隔離しない | 残す | なし | copy_failed |
| コピー失敗 | 隔離しない | 残す | 不完全ファイルは削除を試みる | copy_failed |
| コピー検証失敗 | 隔離しない | 残す | コピー先を削除する | copy_failed |
| 元ファイル削除失敗 | 隔離先にコピーは残す | 残る | 残す | delete_failed |
| 不完全コピー削除失敗 | ログに残す | 残す | 残る可能性あり | rollback_failed |

### 5.3 元ファイル削除失敗時の方針

コピーは成功しているが元ファイル削除に失敗した場合、完全な隔離完了とは扱わない。検出結果画面では「コピー済み、元ファイル削除失敗」と分かる状態にする。

この場合、ユーザーは後から手動で元ファイルを削除できる。

### 5.4 ファイル名衝突時

隔離先に同名ファイルがある場合は、ファイル名末尾に短いハッシュを付与する。

例:

```text
photo.jpg
photo__a1b2c3d4.jpg
```

### 5.5 隔離フォルダ構造

元ファイルの場所を追いやすくするため、隔離フォルダ内にはスキャン日時ごとのフォルダを作る。

```text
quarantine/
  20260527_105500/
    files/
    manifest.json
```

`manifest.json` は人間が見ても分かる簡易一覧として出力する。正式な履歴はSQLiteに保存する。

## 6. 確定事項

1. SQLiteスキーマは本書の粒度で進める。
2. 設定ファイルはJSONで本書の項目から始める。
3. ログは1行JSON形式で出力する。
4. 隔離はコピー検証後に元ファイルを削除する二段階方式で進める。

## 7. 実装モジュール構成

初期実装では、画面、アプリ制御、ファイル処理、検出処理、永続化を分離する。UIから直接ファイル削除やDB更新を行わず、必ずサービス層を通して実行する。

### 7.1 ディレクトリ構成

```text
MediaClinaer/
  src/
    media_clinaer/
      __init__.py
      main.py
      app_context.py
      config/
        __init__.py
        manager.py
        models.py
      logging/
        __init__.py
        logger.py
        events.py
      storage/
        __init__.py
        database.py
        migrations.py
        repositories.py
      scanner/
        __init__.py
        file_collector.py
        metadata_reader.py
        path_utils.py
      analysis/
        __init__.py
        hashing.py
        image_similarity.py
        blur_detector.py
      detection/
        __init__.py
        duplicate_detector.py
        similar_detector.py
        blurry_detector.py
        group_builder.py
      quarantine/
        __init__.py
        planner.py
        executor.py
        manifest.py
      services/
        __init__.py
        scan_service.py
        detection_service.py
        quarantine_service.py
        cache_service.py
      ui/
        __init__.py
        main_window.py
        scan_settings_view.py
        scan_progress_view.py
        results_view.py
        quarantine_result_view.py
      models/
        __init__.py
        media_file.py
        detection_group.py
        scan_session.py
        quarantine_record.py
  tests/
    unit/
    integration/
    fixtures/
```

### 7.2 モジュール責務

| モジュール | 責務 |
| --- | --- |
| `main.py` | アプリ起動、起動時チェック、メインウィンドウ表示 |
| `app_context.py` | アプリフォルダ、完全パス、共有オブジェクトの管理 |
| `config` | `config.json` の読み書き、初期値作成、設定バリデーション |
| `logging` | 1行JSONログ出力、SQLiteイベント保存用のイベント定義 |
| `storage` | SQLite接続、スキーマ作成、DBアクセス |
| `scanner` | フォルダ走査、対象拡張子判定、長いパス処理、メタ情報取得 |
| `analysis` | SHA-256、知覚ハッシュ、ブレスコア計算 |
| `detection` | 完全重複、類似画像、ブレ画像、重複動画のグループ化 |
| `quarantine` | 隔離先パス生成、コピー検証、元ファイル削除、manifest出力 |
| `services` | UIから呼び出すユースケース制御 |
| `ui` | PySide6画面、ユーザー操作、進捗表示 |
| `models` | アプリ内で受け渡すデータ構造 |

### 7.3 依存方向

依存方向は以下を原則とする。

```text
ui
  -> services
    -> scanner / analysis / detection / quarantine / storage / config / logging
      -> models
```

`scanner`、`analysis`、`detection`、`quarantine` は、UIに依存しない。これにより、単体テストと将来のCLI実行をしやすくする。

### 7.4 主要サービス

#### ScanService

スキャン開始からファイル情報保存までを担当する。

主な処理:

- スキャンセッション作成
- 対象フォルダ走査
- キャッシュ確認
- メタ情報取得
- 解析処理呼び出し
- `media_files` と `analysis_cache` 更新
- 進捗通知
- 中断要求の反映

#### DetectionService

保存済み `media_files` をもとに検出グループを作成する。

主な処理:

- 完全重複画像検出
- 完全重複動画検出
- 類似画像検出
- ブレ画像検出
- `detection_groups` と `detection_group_items` 更新

#### QuarantineService

ユーザーが選択したファイルの隔離を担当する。

主な処理:

- 隔離計画作成
- 隔離先パス決定
- コピー
- コピー検証
- 元ファイル削除
- `quarantine_records` 更新
- `manifest.json` 出力

#### CacheService

解析キャッシュの再利用判定を担当する。

主な処理:

- パス、サイズ、更新日時によるキャッシュ一致判定
- stale判定
- キャッシュ更新
- キャッシュ無効化

### 7.5 UI構成

PySide6の画面は、処理ロジックを持たず、サービスへ指示するだけにする。

| 画面 | 役割 |
| --- | --- |
| `MainWindow` | 画面遷移、共通メニュー |
| `ScanSettingsView` | 対象フォルダ、検出設定、隔離先確認 |
| `ScanProgressView` | 進捗、エラー件数、中断 |
| `ResultsView` | 検出結果グループ表示、選択 |
| `QuarantineResultView` | 隔離成功、失敗、ログ参照 |

### 7.6 スレッド方針

スキャン、解析、隔離はUIを固めないためにバックグラウンド実行する。初期実装ではPySide6の `QThread` または `QRunnable` を使う。

UIへ通知する情報:

- 現在処理中のパス
- 処理済み件数
- 検出件数
- エラー件数
- 中断完了

### 7.7 初期実装の優先順

1. `app_context`、`config`、`logging`
2. `storage` とSQLiteスキーマ作成
3. `scanner` とキャッシュ再利用
4. 完全重複検出
5. 最小UI
6. 隔離処理
7. 類似画像検出
8. ブレ画像検出

この順番なら、まず安全なファイル走査と完全重複検出を動かし、その後に画像解析機能を足せる。

### 7.8 確定事項

1. 本書のディレクトリ構成で進める。
2. UIと処理本体を分離する。
3. 初期実装の優先順は本書の順番で進める。

## 8. NASアクセス失敗時の例外処理詳細

NASはローカルディスクより遅く、接続断、権限不足、ファイルロック、パス解決失敗が起きやすい。初期実装では、可能な限り処理を継続し、失敗したフォルダまたはファイルをログとSQLiteイベントに残す。

### 8.1 基本方針

- 対象フォルダへアクセスできない場合は、そのフォルダをスキップする。
- 個別ファイルで失敗した場合は、そのファイルだけスキップする。
- スキャン全体は可能な限り継続する。
- エラーは `app.log` と `app_events` に記録する。
- `media_files.scan_error` または `analysis_cache.last_error` に失敗理由を保存する。
- ユーザーには進捗画面と結果画面でエラー件数を表示する。

### 8.2 エラー分類

| 分類 | 例 | 扱い | ログイベント |
| --- | --- | --- | --- |
| 対象フォルダ未接続 | NAS電源OFF、ネットワーク切断 | 対象フォルダをスキップ | `nas_folder_unavailable` |
| 認証不足 | Windows側で認証されていない | 対象フォルダをスキップ | `nas_permission_denied` |
| フォルダ列挙失敗 | 途中のサブフォルダが読めない | そのフォルダ配下をスキップ | `folder_scan_failed` |
| ファイル読み取り失敗 | ファイルロック、権限不足 | そのファイルをスキップ | `file_scan_failed` |
| メタ情報取得失敗 | サイズ、更新日時が取れない | そのファイルをスキップ | `metadata_read_failed` |
| ハッシュ計算失敗 | 読み取り中に切断 | そのファイルをエラー扱い | `hash_failed` |
| 画像解析失敗 | 壊れた画像、非対応データ | そのファイルをエラー扱い | `image_analysis_failed` |
| 隔離コピー失敗 | コピー中に切断、容量不足 | 元ファイルを残して失敗記録 | `quarantine_copy_failed` |
| 隔離元削除失敗 | 権限不足、ロック | コピー済み、元削除失敗として記録 | `quarantine_delete_failed` |
| 長いパス失敗 | OS制約で処理不可 | そのファイルをスキップ | `long_path_skipped` |

### 8.3 スキャン時の扱い

スキャン開始時に対象フォルダの存在確認と読み取り確認を行う。

対象フォルダが読めない場合:

1. `scan_sessions.error_count` を加算する。
2. `app_events` に対象フォルダ単位のエラーを記録する。
3. その対象フォルダをスキップする。
4. 他の対象フォルダがあれば処理を続ける。

サブフォルダが読めない場合:

1. 読めないサブフォルダ配下をスキップする。
2. `folder_scan_failed` としてログに記録する。
3. 兄弟フォルダの走査は続ける。

### 8.4 解析時の扱い

ファイル読み取り、ハッシュ計算、画像解析で失敗した場合は、そのファイルだけエラー扱いにする。

保存内容:

- `media_files.cache_status = "error"`
- `media_files.scan_error` にエラー要約
- `analysis_cache.last_error` にエラー要約
- `app_events` にイベント記録

失敗したファイルは検出グループには含めない。

### 8.5 隔離時の扱い

隔離時のNASアクセス失敗は、5章のロールバック方針に従う。

重要な扱い:

- コピー失敗時は元ファイルを残す。
- コピー検証失敗時は元ファイルを残し、コピー先削除を試みる。
- 元ファイル削除失敗時はコピー先を残し、`delete_failed` として記録する。
- NAS切断で元ファイル状態が確認できない場合は、ユーザーに「状態確認が必要」と表示する。

### 8.6 リトライ方針

初期実装では自動リトライは最小限にする。

| 処理 | リトライ |
| --- | --- |
| フォルダ存在確認 | なし |
| フォルダ列挙 | なし |
| メタ情報取得 | なし |
| ハッシュ計算 | 1回だけ再試行 |
| 隔離コピー | 1回だけ再試行 |
| 元ファイル削除 | 1回だけ再試行 |

再試行しても失敗した場合はログに残し、処理を継続する。

### 8.7 ユーザー表示

進捗画面:

- 読み取り失敗件数
- スキップ件数
- 最後に発生したエラーの短い説明

結果画面:

- エラー一覧を確認できる
- 対象パス、イベント種別、理由、発生日時を表示する

## 9. テストデータ方針

テストデータは、固定の小さなファイルで再現できるものを `tests/fixtures/` に置く。巨大ファイルや実NASが必要なものは手動テストで扱う。

### 9.1 自動テスト用データ

```text
tests/
  fixtures/
    images/
      duplicate_a.jpg
      duplicate_b.jpg
      similar_a.jpg
      similar_b.jpg
      sharp.jpg
      blurry.jpg
      invalid.jpg
    videos/
      duplicate_a.mp4
      duplicate_b.mp4
    folders/
      nested/
        sample.jpg
```

### 9.2 データ種別

| 種別 | 目的 |
| --- | --- |
| 完全重複画像 | SHA-256一致の検出確認 |
| 完全重複動画 | 動画の完全重複検出確認 |
| 類似画像 | 知覚ハッシュ距離の確認 |
| 鮮明画像 | ブレ判定の非対象確認 |
| ブレ画像 | ブレ候補検出確認 |
| 壊れた画像 | 画像解析失敗時のログ確認 |
| 非対象拡張子 | スキャン対象外判定の確認 |
| 深いフォルダ | 再帰スキャン確認 |

### 9.3 手動テスト用データ

手動テストでは以下を用意する。

- NAS共有フォルダ上の画像と動画
- ネットワークドライブ割り当てパス
- UNCパス
- 長いパスのファイル
- 読み取り専用ファイル
- 他アプリで開いてロックしたファイル
- 大きめの動画ファイル

### 9.4 テストデータの管理方針

- 自動テスト用データは小さく保つ。
- 実写真や個人情報を含むデータはリポジトリに入れない。
- 大きい動画、NAS用データ、権限テスト用データは手動準備とする。
- テスト用に生成できる画像は、テスト実行時に一時フォルダへ生成してもよい。

## 10. 単体テストと手動テストの範囲

### 10.1 単体テスト対象

単体テストはUIに依存しない処理を中心にする。

| 対象 | 確認内容 |
| --- | --- |
| `config` | 初期設定作成、読み込み、バリデーション |
| `logging` | 1行JSONログ形式、必須項目 |
| `storage` | SQLiteスキーマ作成、基本CRUD |
| `scanner.path_utils` | 拡張子判定、パス正規化、storage_type判定 |
| `scanner.file_collector` | 再帰スキャン、非対象拡張子除外 |
| `analysis.hashing` | SHA-256計算、読み取り失敗時の例外 |
| `analysis.image_similarity` | 知覚ハッシュ作成、距離計算 |
| `analysis.blur_detector` | ブレスコア計算 |
| `detection.duplicate_detector` | ハッシュ一致グループ作成 |
| `detection.group_builder` | 検出グループ生成 |
| `quarantine.planner` | 隔離先パス生成、衝突時ハッシュ付与 |
| `quarantine.executor` | コピー成功、コピー失敗、削除失敗 |
| `services.cache_service` | キャッシュ再利用、stale判定 |

### 10.2 結合テスト対象

| 対象 | 確認内容 |
| --- | --- |
| スキャンからDB保存 | `scan_sessions`、`media_files`、`analysis_cache` が更新される |
| 完全重複検出 | `detection_groups`、`detection_group_items` が作成される |
| 隔離処理 | `quarantine_records` と `manifest.json` が作成される |
| キャッシュ再利用 | 2回目スキャンで `cache_status = reused` になる |
| エラーログ | 失敗時に `app.log` と `app_events` へ記録される |

### 10.3 手動テスト対象

| 対象 | 確認内容 |
| --- | --- |
| PySide6 UI | 画面遷移、ボタン、進捗表示 |
| NASスキャン | UNCパス、ネットワークドライブで走査できる |
| NAS切断 | 切断時に処理継続または適切にスキップされる |
| 隔離操作 | コピー検証後に元ファイルが削除される |
| 元ファイル削除失敗 | UIに「コピー済み、元削除失敗」が出る |
| 大量ファイル | 進捗、応答性、処理時間 |
| 長いパス | スキップとログ記録 |
| 画像判定精度 | 類似画像、ブレ画像の目視確認 |

### 10.4 初期版で必須にするテスト

初期版では以下を必須とする。

- 設定ファイルの読み書き
- SQLiteスキーマ作成
- フォルダスキャン
- 完全重複検出
- キャッシュ再利用
- 隔離コピー成功
- 隔離コピー失敗
- 隔離元削除失敗
- 1行JSONログ出力

### 10.5 確定事項

1. NAS例外処理は本書の方針で進める。
2. テストデータは自動テスト用と手動テスト用に分ける。
3. 単体テストと手動テストの範囲は本書の内容で進める。
