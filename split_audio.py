#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
音声ファイルを3分割するスクリプト

使用方法:
    python split_audio.py IMG_3068.m4a
"""

import os
import sys
from pathlib import Path

def check_ffmpeg():
    """ffmpegが利用可能か確認"""
    import subprocess
    try:
        result = subprocess.run(
            ['ffmpeg', '-version'],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False

def get_audio_duration(input_file):
    """音声ファイルの長さ（秒）を取得"""
    import subprocess
    import json
    
    try:
        # ffprobeを使用してファイル情報を取得
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            str(input_file)
        ]
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            encoding='utf-8',
            errors='replace',
            timeout=30
        )
        
        if result.returncode != 0:
            raise Exception(f"ffprobeエラー: {result.stderr}")
        
        if not result.stdout:
            raise Exception("ffprobeの出力が空です")
        
        data = json.loads(result.stdout)
        duration = float(data['format']['duration'])
        return duration
    except Exception as e:
        print(f"エラー: ファイルの長さを取得できませんでした: {e}")
        return None

def split_audio_ffmpeg(input_file, output_dir=None):
    """ffmpegを使用して音声ファイルを3分割"""
    import subprocess
    
    input_path = Path(input_file)
    if not input_path.exists():
        print(f"エラー: ファイルが見つかりません: {input_file}")
        return False
    
    # 出力ディレクトリの設定
    if output_dir is None:
        output_dir = input_path.parent
    else:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
    
    # ファイルの長さを取得
    duration = get_audio_duration(input_file)
    if duration is None:
        return False
    
    print(f"ファイルの長さ: {duration:.2f}秒")
    
    # 3分割の各セグメントの長さ
    segment_duration = duration / 3
    
    # 出力ファイル名のベース
    base_name = input_path.stem
    
    # 3つのセグメントを作成
    segments = [
        {
            'start': 0,
            'end': segment_duration,
            'output': output_dir / f"{base_name}_part1.m4a"
        },
        {
            'start': segment_duration,
            'end': segment_duration * 2,
            'output': output_dir / f"{base_name}_part2.m4a"
        },
        {
            'start': segment_duration * 2,
            'end': duration,
            'output': output_dir / f"{base_name}_part3.m4a"
        }
    ]
    
    # 各セグメントを抽出
    for i, segment in enumerate(segments, 1):
        print(f"\nパート{i}を作成中... ({segment['start']:.2f}秒 ～ {segment['end']:.2f}秒)")
        
        cmd = [
            'ffmpeg',
            '-i', str(input_path),
            '-ss', str(segment['start']),
            '-t', str(segment['end'] - segment['start']),
            '-c', 'copy',  # 再エンコードせずにコピー（高速）
            '-y',  # 上書き確認なし
            str(segment['output'])
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=300  # 5分のタイムアウト
            )
            
            if result.returncode == 0:
                print(f"[OK] パート{i}を作成しました: {segment['output']}")
            else:
                print(f"[NG] パート{i}の作成に失敗しました:")
                print(f"  エラー: {result.stderr}")
                return False
        except subprocess.TimeoutExpired:
            print(f"[NG] パート{i}の作成がタイムアウトしました")
            return False
        except Exception as e:
            print(f"[NG] パート{i}の作成中にエラーが発生しました: {e}")
            return False
    
    print(f"\n[OK] すべてのパートの作成が完了しました！")
    return True

def main():
    """メイン処理"""
    # ファイル名の取得
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    else:
        input_file = "IMG_3068.m4a"
    
    # 絶対パスに変換
    script_dir = Path(__file__).parent
    input_path = script_dir / input_file
    
    if not input_path.exists():
        print(f"エラー: ファイルが見つかりません: {input_path}")
        print(f"現在のディレクトリ: {script_dir}")
        return 1
    
    # ffmpegの確認
    if not check_ffmpeg():
        print("=" * 70)
        print("エラー: ffmpegが見つかりません")
        print("=" * 70)
        print("\nffmpegをインストールする方法:")
        print("\n【推奨】Windows用ポータブル版をダウンロード:")
        print("1. 以下のURLからffmpegをダウンロード:")
        print("   https://www.gyan.dev/ffmpeg/builds/")
        print("   「ffmpeg-release-essentials.zip」をダウンロード")
        print("\n2. ダウンロードしたzipファイルを解凍")
        print("\n3. 解凍したフォルダ内の「bin」フォルダのパスを環境変数PATHに追加")
        print("   例: C:\\ffmpeg\\bin")
        print("\n4. 新しいコマンドプロンプトを開いて、以下で確認:")
        print("   ffmpeg -version")
        print("\n【その他の方法】")
        print("- Chocolatey: choco install ffmpeg (管理者権限が必要)")
        print("- Scoop: scoop install ffmpeg (Scoopがインストールされている場合)")
        print("=" * 70)
        print("\nffmpegをインストールした後、このスクリプトを再度実行してください。")
        return 1
    
    print(f"音声ファイルを3分割します: {input_path}")
    print("-" * 60)
    
    # 分割実行
    success = split_audio_ffmpeg(input_path)
    
    if success:
        return 0
    else:
        return 1

if __name__ == "__main__":
    sys.exit(main())

