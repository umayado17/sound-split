#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
音声ファイル分割APIサーバー（Cloud Run用）

目次:
1. インポートと設定
2. エラーハンドリング
3. ヘルスチェックエンドポイント
4. 音声分割エンドポイント
5. メイン処理
"""

import os
import tempfile
import zipfile
from pathlib import Path
from typing import List
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import io

from audio_utils import (
    check_ffmpeg,
    split_audio_smart,
    MAX_FILE_SIZE_MB,
    DEFAULT_SEGMENT_DURATION_SEC
)


app = FastAPI(
    title="音声ファイル分割API",
    description="音声ファイルを10分単位または32MB以下に分割してzip圧縮して返すAPI",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 環境変数から設定を取得（デフォルト値あり）
MAX_UPLOAD_SIZE_MB = float(os.getenv("MAX_UPLOAD_SIZE_MB", "100"))  # アップロード最大サイズ
SEGMENT_DURATION_SEC = float(os.getenv("SEGMENT_DURATION_SEC", str(DEFAULT_SEGMENT_DURATION_SEC)))


@app.get("/")
async def root():
    """ルートエンドポイント（ヘルスチェック）"""
    return {
        "status": "ok",
        "message": "音声ファイル分割API",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    """ヘルスチェックエンドポイント"""
    ffmpeg_available = check_ffmpeg()
    return {
        "status": "healthy" if ffmpeg_available else "unhealthy",
        "ffmpeg_available": ffmpeg_available
    }


@app.post("/split-audio")
async def split_audio(file: UploadFile = File(...)):
    """
    音声ファイルを10分単位または32MB以下に分割してzip圧縮して返す
    
    パラメータ:
    - file: アップロードする音声ファイル（m4a, mp3, wav等）
    
    レスポンス:
    - zipファイル（分割された音声ファイルを含む）
    """
    # ffmpegの確認
    if not check_ffmpeg():
        raise HTTPException(
            status_code=503,
            detail="ffmpegが利用できません。サーバー設定を確認してください。"
        )
    
    # ファイルサイズの確認
    file_content = await file.read()
    file_size_mb = len(file_content) / (1024 * 1024)
    
    if file_size_mb > MAX_UPLOAD_SIZE_MB:
        raise HTTPException(
            status_code=413,
            detail=f"ファイルサイズが大きすぎます。最大{MAX_UPLOAD_SIZE_MB}MBまで対応しています。"
        )
    
    # 一時ディレクトリを作成
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # アップロードされたファイルを保存
        input_file = temp_path / file.filename
        with open(input_file, "wb") as f:
            f.write(file_content)
        
        # 出力ディレクトリを作成
        output_dir = temp_path / "output"
        output_dir.mkdir()
        
        # 音声ファイルを分割
        try:
            output_files = split_audio_smart(
                input_file,
                output_dir,
                segment_duration_sec=SEGMENT_DURATION_SEC,
                max_size_mb=MAX_FILE_SIZE_MB
            )
            
            if not output_files:
                raise HTTPException(
                    status_code=500,
                    detail="音声ファイルの分割に失敗しました。"
                )
            
            # zipファイルを作成
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for output_file in output_files:
                    zip_file.write(output_file, output_file.name)
            
            zip_buffer.seek(0)
            
            # zipファイルのサイズを確認
            zip_size_mb = len(zip_buffer.getvalue()) / (1024 * 1024)
            
            #if zip_size_mb > MAX_FILE_SIZE_MB:
                # zipファイルが32MBを超える場合は警告を返す
                # ただし、Cloud Runのレスポンスサイズ制限（32MB）を考慮
                #raise HTTPException(
                    #status_code=413,
                    #detail=f"分割後のzipファイルサイズ（{zip_size_mb:.2f}MB）が32MBを超えています。"
                #)
            
            # レスポンスを返す
            return StreamingResponse(
                io.BytesIO(zip_buffer.getvalue()),
                media_type="application/zip",
                headers={
                    "Content-Disposition": f"attachment; filename={Path(file.filename).stem}_split.zip"
                }
            )
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"処理中にエラーが発生しました: {str(e)}"
            )


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)

