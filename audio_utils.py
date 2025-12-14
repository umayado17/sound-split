#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
音声ファイル分割用のユーティリティ関数

目次:
1. check_ffmpeg - ffmpegの確認
2. get_audio_duration - 音声ファイルの長さ取得
3. get_file_size_mb - ファイルサイズ取得（MB）
4. split_audio_by_duration - 指定時間で分割
5. split_audio_by_size_limit - 32MB以下で分割
6. split_audio_smart - 10分単位または32MB以下で分割
"""

import os
import subprocess
import json
from pathlib import Path
from typing import List, Dict, Optional

# 定数
MAX_FILE_SIZE_MB = 32  # NotebookLMの制限
DEFAULT_SEGMENT_DURATION_SEC = 600  # 10分 = 600秒


def check_ffmpeg() -> bool:
    """ffmpegが利用可能か確認"""
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


def get_audio_duration(input_file: Path) -> Optional[float]:
    """音声ファイルの長さ（秒）を取得"""
    try:
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


def get_file_size_mb(file_path: Path) -> float:
    """ファイルサイズをMBで取得"""
    return file_path.stat().st_size / (1024 * 1024)


def split_audio_segment(
    input_file: Path,
    start_time: float,
    duration: float,
    output_file: Path
) -> bool:
    """音声ファイルの指定セグメントを抽出"""
    cmd = [
        'ffmpeg',
        '-i', str(input_file),
        '-ss', str(start_time),
        '-t', str(duration),
        '-c', 'copy',  # 再エンコードせずにコピー（高速）
        '-y',  # 上書き確認なし
        str(output_file)
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
        
        if result.returncode != 0:
            print(f"エラー: {result.stderr}")
            return False
        return True
    except subprocess.TimeoutExpired:
        print(f"タイムアウト: セグメントの作成がタイムアウトしました")
        return False
    except Exception as e:
        print(f"エラー: {e}")
        return False


def split_audio_by_duration(
    input_file: Path,
    output_dir: Path,
    segment_duration_sec: float = DEFAULT_SEGMENT_DURATION_SEC
) -> List[Path]:
    """音声ファイルを指定時間で分割"""
    duration = get_audio_duration(input_file)
    if duration is None:
        return []
    
    output_dir.mkdir(parents=True, exist_ok=True)
    base_name = input_file.stem
    output_files = []
    
    start_time = 0.0
    part_num = 1
    
    while start_time < duration:
        end_time = min(start_time + segment_duration_sec, duration)
        segment_duration = end_time - start_time
        
        output_file = output_dir / f"{base_name}_part{part_num:03d}.m4a"
        
        if split_audio_segment(input_file, start_time, segment_duration, output_file):
            output_files.append(output_file)
            part_num += 1
        else:
            break
        
        start_time = end_time
    
    return output_files


def split_audio_by_size_limit(
    input_file: Path,
    output_dir: Path,
    max_size_mb: float = MAX_FILE_SIZE_MB
) -> List[Path]:
    """音声ファイルを32MB以下になるように分割"""
    duration = get_audio_duration(input_file)
    if duration is None:
        return []
    
    # 元のファイルサイズから、1秒あたりのサイズを推定
    original_size_mb = get_file_size_mb(input_file)
    bytes_per_second = (original_size_mb * 1024 * 1024) / duration
    
    # 32MBに収まる最大秒数を計算（マージンを考慮して90%に設定）
    max_duration_per_segment = (max_size_mb * 1024 * 1024 * 0.9) / bytes_per_second
    
    output_dir.mkdir(parents=True, exist_ok=True)
    base_name = input_file.stem
    output_files = []
    
    start_time = 0.0
    part_num = 1
    
    while start_time < duration:
        # セグメントの長さを計算
        segment_duration = min(max_duration_per_segment, duration - start_time)
        end_time = start_time + segment_duration
        
        output_file = output_dir / f"{base_name}_part{part_num:03d}.m4a"
        
        if split_audio_segment(input_file, start_time, segment_duration, output_file):
            # 実際のファイルサイズを確認
            actual_size_mb = get_file_size_mb(output_file)
            
            # 32MBを超えている場合は、より短いセグメントで再試行
            if actual_size_mb > max_size_mb:
                output_file.unlink()  # 削除
                # より短いセグメントで再計算
                max_duration_per_segment = max_duration_per_segment * (max_size_mb / actual_size_mb) * 0.9
                segment_duration = min(max_duration_per_segment, duration - start_time)
                end_time = start_time + segment_duration
                
                if not split_audio_segment(input_file, start_time, segment_duration, output_file):
                    break
            
            output_files.append(output_file)
            part_num += 1
        else:
            break
        
        start_time = end_time
    
    return output_files


def split_audio_smart(
    input_file: Path,
    output_dir: Path,
    segment_duration_sec: float = DEFAULT_SEGMENT_DURATION_SEC,
    max_size_mb: float = MAX_FILE_SIZE_MB
) -> List[Path]:
    """
    音声ファイルを10分単位で分割し、32MBを超える場合はさらに分割
    
    優先順位:
    1. 10分単位で分割
    2. 各セグメントが32MBを超える場合は、32MB以下になるように再分割
    """
    duration = get_audio_duration(input_file)
    if duration is None:
        return []
    
    output_dir.mkdir(parents=True, exist_ok=True)
    base_name = input_file.stem
    output_files = []
    
    # まず10分単位で分割
    start_time = 0.0
    part_num = 1
    
    while start_time < duration:
        end_time = min(start_time + segment_duration_sec, duration)
        segment_duration = end_time - start_time
        
        temp_output_file = output_dir / f"{base_name}_temp_part{part_num:03d}.m4a"
        
        if not split_audio_segment(input_file, start_time, segment_duration, temp_output_file):
            break
        
        # ファイルサイズを確認
        file_size_mb = get_file_size_mb(temp_output_file)
        
        if file_size_mb <= max_size_mb:
            # 32MB以下ならそのまま使用
            final_output_file = output_dir / f"{base_name}_part{part_num:03d}.m4a"
            temp_output_file.rename(final_output_file)
            output_files.append(final_output_file)
            part_num += 1
        else:
            # 32MBを超えている場合は、さらに分割
            temp_output_file.unlink()  # 一時ファイルを削除
            
            # このセグメントを32MB以下になるように分割
            sub_segments = split_audio_by_size_limit_for_segment(
                input_file,
                output_dir,
                start_time,
                end_time,
                base_name,
                part_num,
                max_size_mb
            )
            
            if not sub_segments:
                break
            
            output_files.extend(sub_segments)
            part_num += len(sub_segments)
        
        start_time = end_time
    
    return output_files


def split_audio_by_size_limit_for_segment(
    input_file: Path,
    output_dir: Path,
    start_time: float,
    end_time: float,
    base_name: str,
    start_part_num: int,
    max_size_mb: float
) -> List[Path]:
    """指定時間範囲を32MB以下になるように分割"""
    segment_duration = end_time - start_time
    
    # このセグメントの推定サイズを計算
    original_size_mb = get_file_size_mb(input_file)
    total_duration = get_audio_duration(input_file)
    if total_duration is None:
        return []
    
    bytes_per_second = (original_size_mb * 1024 * 1024) / total_duration
    max_duration_per_segment = (max_size_mb * 1024 * 1024 * 0.9) / bytes_per_second
    
    output_files = []
    current_start = start_time
    part_num = start_part_num
    
    while current_start < end_time:
        segment_len = min(max_duration_per_segment, end_time - current_start)
        current_end = current_start + segment_len
        
        output_file = output_dir / f"{base_name}_part{part_num:03d}.m4a"
        
        if not split_audio_segment(input_file, current_start, segment_len, output_file):
            break
        
        # 実際のファイルサイズを確認
        actual_size_mb = get_file_size_mb(output_file)
        
        if actual_size_mb > max_size_mb:
            output_file.unlink()
            max_duration_per_segment = max_duration_per_segment * (max_size_mb / actual_size_mb) * 0.9
            continue
        
        output_files.append(output_file)
        part_num += 1
        current_start = current_end
    
    return output_files

