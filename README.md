# 音声ファイル分割API

iOSで撮影したビデオから抽出した音声ファイルを、NotebookLMにアップロード可能なサイズ（32MB以下）に分割するCloud Run APIサーバーです。

## 機能

- 音声ファイルを10分単位で分割
- 各セグメントが32MBを超える場合は、さらに32MB以下になるように分割
- 分割されたファイルをzip圧縮して返却
- iOSショートカット機能から呼び出し可能

## 要件

- Google Cloud Platform（GCP）アカウント
- gcloud CLIがインストールされていること
- Dockerがインストールされていること（ローカルテスト用）

## gcloud CLIのインストール（Windows）

`gcloud`コマンドが見つからない場合は、以下の手順でインストールしてください：

### 方法1: インストーラーを使用（推奨）

1. [Google Cloud SDKのダウンロードページ](https://cloud.google.com/sdk/docs/install)にアクセス
2. 「Windows (64-bit)」を選択してインストーラーをダウンロード
3. インストーラーを実行してインストール
4. 新しいターミナルを開いて、以下で確認：
   ```bash
   gcloud --version
   ```

### 方法2: PowerShell経由でインストール

```powershell
# PowerShellを管理者権限で開いて実行
(New-Object Net.WebClient).DownloadFile("https://dl.google.com/dl/cloudsdk/channels/rapid/GoogleCloudSDKInstaller.exe", "$env:Temp\GoogleCloudSDKInstaller.exe")
& $env:Temp\GoogleCloudSDKInstaller.exe
```

### インストール後の初期設定

```bash
# ログイン
gcloud auth login

# プロジェクトを設定
gcloud config set project split-sound

# デフォルトリージョンを設定
gcloud config set run/region asia-northeast1
```

## デプロイ手順

### 1. GCPプロジェクトの設定

```bash
# GCPプロジェクトIDを設定
export PROJECT_ID=split-sound
gcloud config set project $PROJECT_ID

# Cloud Run APIを有効化
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com
```

### 2. コンテナイメージのビルドとプッシュ

```bash
# コンテナイメージをビルド
gcloud builds submit --tag gcr.io/$PROJECT_ID/audio-splitter

# または、手動でDockerビルド
docker build -t gcr.io/$PROJECT_ID/audio-splitter .
docker push gcr.io/$PROJECT_ID/audio-splitter
```

### 3. Cloud Runにデプロイ

```bash
gcloud run deploy audio-splitter \
  --image gcr.io/$PROJECT_ID/audio-splitter \
  --platform managed \
  --region asia-northeast1 \
  --allow-unauthenticated \
  --memory 2Gi \
  --timeout 900 \
  --max-instances 10 \
  --set-env-vars "MAX_UPLOAD_SIZE_MB=100,SEGMENT_DURATION_SEC=600"
```

### 4. APIエンドポイントの確認

デプロイが完了すると、以下のようなURLが表示されます：

```
https://audio-splitter-xxxxx-an.a.run.app
```

このURLをメモしておいてください。iOSショートカットで使用します。

## API仕様

### ヘルスチェック

```bash
GET /health
```

レスポンス例：
```json
{
  "status": "healthy",
  "ffmpeg_available": true
}
```

### 音声ファイル分割

```bash
POST /split-audio
Content-Type: multipart/form-data
```

**リクエスト:**
- `file`: 音声ファイル（m4a, mp3, wav等）

**レスポンス:**
- Content-Type: `application/zip`
- 分割された音声ファイルを含むzipファイル

**エラーレスポンス:**
- `413`: ファイルサイズが大きすぎる、またはzipファイルが32MBを超える
- `500`: 処理中にエラーが発生
- `503`: ffmpegが利用できない

## iOSショートカットでの使用方法

### ショートカットの作成手順

1. iOSの「ショートカット」アプリを開く
2. 「+」ボタンで新しいショートカットを作成
3. 以下のアクションを追加：

```
1. 「ファイルを選択」アクション
   - 音声ファイルを選択

2. 「URLの内容を取得」アクション
   - メソッド: POST
   - URL: https://your-api-url.run.app/split-audio
   - ヘッダー:
     - Content-Type: multipart/form-data
   - リクエスト本文: ファイル（上で選択したファイル）

3. 「ZIPを展開」アクション
   - 上で取得したzipファイルを展開

4. 「ファイルを保存」アクション
   - 展開されたファイルを「ファイル」アプリに保存
```

### ショートカットの詳細設定

「URLの内容を取得」アクションの設定：

- **URL**: デプロイ時に取得したAPIエンドポイントURL + `/split-audio`
- **メソッド**: POST
- **リクエスト本文**: ファイル
- **ファイル**: 変数から選択（「ファイルを選択」で選択したファイル）

## ローカルテスト

### Dockerでローカル実行

```bash
# イメージをビルド
docker build -t audio-splitter .

# コンテナを起動
docker run -p 8080:8080 audio-splitter

# 別のターミナルでテスト
curl -X POST http://localhost:8080/split-audio \
  -F "file=@IMG_3068.m4a" \
  -o output.zip
```

### Pythonで直接実行

```bash
# 依存関係をインストール
pip install -r requirements.txt

# ffmpegがインストールされていることを確認
ffmpeg -version

# サーバーを起動
python app.py

# 別のターミナルでテスト
curl -X POST http://localhost:8080/split-audio \
  -F "file=@IMG_3068.m4a" \
  -o output.zip
```

## 環境変数

以下の環境変数で動作をカスタマイズできます：

- `MAX_UPLOAD_SIZE_MB`: アップロード可能な最大ファイルサイズ（MB、デフォルト: 100）
- `SEGMENT_DURATION_SEC`: 分割するセグメントの長さ（秒、デフォルト: 600 = 10分）
- `PORT`: サーバーのポート番号（デフォルト: 8080、Cloud Runでは自動設定）

## 制限事項

- Cloud Runのリクエストサイズ制限: 32MB
- Cloud Runのレスポンスサイズ制限: 32MB
- 元のファイルが非常に大きい場合、分割後のzipファイルも32MBを超える可能性があります
- その場合は、元のファイルを事前に分割するか、別の方法を検討してください

## トラブルシューティング

### ffmpegが利用できないエラー

- Dockerfileでffmpegが正しくインストールされているか確認
- Cloud Runのログを確認: `gcloud run services logs read audio-splitter`

### タイムアウトエラー

- Cloud Runのタイムアウト設定を増やす（`--timeout`オプション）
- メモリを増やす（`--memory`オプション）

### ファイルサイズエラー

- 元のファイルサイズを確認
- `MAX_UPLOAD_SIZE_MB`環境変数を調整

## ライセンス

このプロジェクトはMITライセンスの下で公開されています。

