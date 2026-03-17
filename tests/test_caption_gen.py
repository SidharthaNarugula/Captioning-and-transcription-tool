#!/usr/bin/env python
# Direct test of caption generation

from datetime import timedelta
import pysrt
import os

def test_generate_srt_from_text():
    """Test the caption generation from text"""
    text = "Hello world this is a test of the caption generation system and it should work properly"
    
    subtitles = pysrt.SubRipFile()
    words = text.split()
    
    if not words:
        print("No words found")
        return None
    
    word_duration_ms = 2000
    
    current_line = ""
    current_start_ms = 0
    index = 1
    max_chars_per_line = 42
    
    for i, word in enumerate(words):
        if current_line:
            test_line = f"{current_line} {word}"
        else:
            test_line = word
        
        if len(test_line) > max_chars_per_line and current_line:
            word_count = len(current_line.split())
            duration_for_block = word_count * (word_duration_ms / max(1, len(words)))
            
            subtitle = pysrt.SubRipItem()
            subtitle.index = index
            subtitle.start = timedelta(milliseconds=current_start_ms)
            subtitle.end = timedelta(milliseconds=current_start_ms + max(duration_for_block, 1000))
            subtitle.text = current_line
            subtitles.append(subtitle)
            
            print(f"Added subtitle {index}: {current_line}")
            
            current_start_ms = current_start_ms + max(duration_for_block, 1000)
            current_line = word
            index += 1
        else:
            current_line = test_line
    
    if current_line:
        word_count = len(current_line.split())
        duration_for_block = word_count * (word_duration_ms / max(1, len(words)))
        
        subtitle = pysrt.SubRipItem()
        subtitle.index = index
        subtitle.start = timedelta(milliseconds=current_start_ms)
        subtitle.end = timedelta(milliseconds=current_start_ms + max(duration_for_block, 1000))
        subtitle.text = current_line
        subtitles.append(subtitle)
        
        print(f"Added subtitle {index}: {current_line}")
    
    print(f"\n✓ Total subtitles created: {len(subtitles)}")
    
    # Try to save
    test_srt_path = "c:/backupDT/captions/test_output.srt"
    os.makedirs(os.path.dirname(test_srt_path), exist_ok=True)
    
    try:
        subtitles.save(test_srt_path, encoding='utf-8')
        print(f"✓ Successfully saved to {test_srt_path}")
        
        # Try to read it back
        with open(test_srt_path, 'r', encoding='utf-8') as f:
            content = f.read()
            print(f"\nSRT File Content:\n{content}")
        
        return True
    except Exception as e:
        print(f"✗ Error saving: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    try:
        test_generate_srt_from_text()
        print("\n✓ Test passed!")
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
