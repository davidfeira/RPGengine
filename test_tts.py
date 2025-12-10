"""Quick TTS test to debug issues"""
from tts import get_tts
import time

print("Initializing TTS...")
tts = get_tts()
tts.set_enabled(True)

print(f"TTS enabled: {tts.enabled}")
print(f"TTS engine: {tts.engine}")
print(f"Available voices: {len(tts.voices)}")

print("\n=== Test 1: First speech ===")
print("Speaking: 'First message'")
tts.speak("First message", blocking=False, interrupt=True)
print(f"After first speak - speech_id: {tts._speech_id}, current_speech_id: {tts._current_speech_id}")

time.sleep(2)

print("\n=== Test 2: Second speech (should interrupt) ===")
print("Speaking: 'Second message'")
tts.speak("Second message", blocking=False, interrupt=True)
print(f"After second speak - speech_id: {tts._speech_id}, current_speech_id: {tts._current_speech_id}")

time.sleep(2)

print("\n=== Test 3: Third speech ===")
print("Speaking: 'Third message'")
tts.speak("Third message", blocking=False, interrupt=True)
print(f"After third speak - speech_id: {tts._speech_id}, current_speech_id: {tts._current_speech_id}")

time.sleep(3)
print("\nTest complete!")
