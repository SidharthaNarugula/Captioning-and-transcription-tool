#!/usr/bin/env python
# Test caption generation

import sys
sys.path.insert(0, 'c:/backupDT')

from datetime import timedelta
import pysrt

print("Testing pysrt functionality...")

try:
    # Test basic SubRipItem creation
    subtitles = pysrt.SubRipFile()
    
    item = pysrt.SubRipItem()
    item.index = 1
    item.start = timedelta(milliseconds=0)
    item.end = timedelta(milliseconds=2000)
    item.text = "Test caption"
    
    subtitles.append(item)
    
    print(f"✓ Successfully created subtitle item")
    print(f"✓ Item count: {len(subtitles)}")
    print(f"✓ Item: {item}")
    
    # Test saving
    import tempfile
    import os
    
    with tempfile.TemporaryDirectory() as tmpdir:
        test_path = os.path.join(tmpdir, "test.srt")
        subtitles.save(test_path, encoding='utf-8')
        
        # Read it back
        loaded = pysrt.load(test_path, encoding='utf-8')
        print(f"✓ Successfully saved and loaded SRT file")
        print(f"✓ Loaded {len(loaded)} items")
        print(f"✓ First item text: {loaded[0].text}")
    
    print("\n✓ All tests passed!")
    
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
