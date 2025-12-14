# Python 3.11のベースイメージを使用
FROM python:3.11-slim

# 作業ディレクトリを設定
WORKDIR /app

# システムパッケージの更新とffmpegのインストール
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Python依存関係をコピーしてインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションコードをコピー
COPY app.py audio_utils.py ./

# ポート8080を公開（Cloud Runのデフォルト）
EXPOSE 8080

# 環境変数の設定
ENV PORT=8080
ENV PYTHONUNBUFFERED=1

# アプリケーションを起動
CMD ["python", "app.py"]

