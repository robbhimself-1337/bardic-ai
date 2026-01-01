# Bardic AI - Hardware Upgrade & Architecture Plan

## Overview

This document outlines the planned architecture when the RTX 3090 (24GB VRAM) is added alongside the existing RTX 3060 (12GB VRAM), enabling a dual-GPU setup optimized for real-time D&D gameplay.

## Current Limitations

- Single 12GB GPU trying to run LLM + Whisper + TTS
- Qwen 14B struggles with complex multi-constraint tasks
- Hallucination issues (invents NPCs, changes plot details)
- TTS quality is mediocre (Coqui XTTS v2)

## Target Architecture

### GPU Assignment

```
┌─────────────────────────────────────────────────────────────┐
│                    RTX 3090 (24GB)                          │
│                    LLM Powerhouse                           │
├─────────────────────────────────────────────────────────────┤
│  Expert 7B Q4 (Fine-tuned)     │  ~5GB   │  Always loaded  │
│  General 22B Q4 (Fallback)     │  ~14GB  │  Always loaded  │
│  Reserved                       │  ~5GB   │  Headroom       │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    RTX 3060 (12GB)                          │
│                    Voice Stack                              │
├─────────────────────────────────────────────────────────────┤
│  Whisper (small/medium)        │  ~2GB   │  Always loaded  │
│  Premium TTS                   │  ~6-8GB │  Always loaded  │
│  Reserved                       │  ~2-4GB │  Headroom       │
└─────────────────────────────────────────────────────────────┘
```

### Request Flow

```
Player speaks into microphone
         │
         ▼
┌─────────────────┐
│ Whisper (3060)  │ → Transcribes speech to text
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Expert 7B       │ → Fine-tuned D&D specialist
│ (3090)          │    Handles ~90% of requests
└────────┬────────┘
         │
    Edge case detected?
         │
    ┌────┴────────────────┐
    │ No                  │ Yes
    ▼                     ▼
┌─────────┐      ┌─────────────────┐
│ Return  │      │ General 22B     │ → Full context dump
│ response│      │ (3090)          │    Handles unusual situations
└────┬────┘      └────────┬────────┘
     │                    │
     └──────────┬─────────┘
                ▼
┌─────────────────┐
│ Premium TTS     │ → High-quality voice synthesis
│ (3060)          │
└────────┬────────┘
         │
         ▼
Player hears response
```

## Model Routing Strategy

### Expert Model (7B Fine-tuned)

**Purpose:** Handle standard D&D gameplay fast and consistently

**Training Focus:**
- Correct speaker tag usage: `[DM]` vs `[NPC Name]`
- Stay in character with defined NPC personalities
- Never hallucinate NPCs (only reference those in scene)
- Follow story structure from campaign data
- Appropriate response length (2-4 sentences)

**Expected Performance:**
- Response time: ~2-4 seconds
- Accuracy on standard requests: 95%+

### General Model (22B)

**Purpose:** Handle edge cases the expert can't

**Triggered When:**
- Player input way outside normal gameplay
- Expert response shows uncertainty/hedging
- Missing expected speaker tags
- Player explicitly asks for unusual help

**Handoff Process:**
```python
response = expert_model(prompt)

if is_edge_case(response, player_input):
    full_context = {
        'game_state': state_manager.to_dict(),
        'recent_history': last_5_exchanges,
        'player_input': player_input,
        'failed_response': response
    }
    response = general_model(build_edge_case_prompt(full_context))

return response
```

**Expected Performance:**
- Response time: ~6-10 seconds
- Only fires for ~10% of requests

## TTS Upgrade Options

With ~6-8GB available on the 3060, these are viable upgrades:

| Model | VRAM | Quality | Speed | Best For |
|-------|------|---------|-------|----------|
| Fish Speech | ~4-6GB | Great | Fast | Balanced performance |
| GPT-SoVITS | ~4-6GB | Excellent | Medium | Best voice cloning |
| StyleTTS2 | ~2-4GB | Great | Fast | Low VRAM, good quality |
| MARS5-TTS | ~6-8GB | Excellent | Medium | Near studio quality |

**Advanced Option:** Run multiple TTS models
- One voice optimized for DM narration
- Different voices for different NPCs
- Swap based on speaker tag

## Fine-Tuning Plan

### Phase 1: Data Collection
- Play sessions generate input/output examples
- Curate dataset of good vs bad responses
- Target: 1000+ quality examples minimum

### Training Examples Format:
```
Context: Location: Rusty Dragon Tavern. NPCs present: Ameiko Kaijitsu. 
Player says: "Can I help?"

Good: [Ameiko Kaijitsu] "Oh, thank you for asking. These are dark times..."
Bad: [DM] Ameiko says "Oh, thank you for asking..."
Bad: [Ameiko Kaijitsu] "Let me introduce you to Aldren..." (hallucinated NPC)
```

### Phase 2: LoRA Fine-tuning
- Base model: Qwen 2.5 7B or Mistral 7B
- Method: LoRA (Low-Rank Adaptation)
- Hardware: Can train on 3090 (24GB sufficient for 7B LoRA)

### Phase 3: Evaluation
- Test against held-out examples
- Measure: speaker tag accuracy, hallucination rate, response quality
- Iterate on training data based on failures

## Performance Targets

| Metric | Current | Target |
|--------|---------|--------|
| Response latency (normal) | 8-12s | 3-5s |
| Response latency (edge case) | N/A | 8-12s |
| Speaker tag accuracy | ~70% | 95%+ |
| NPC hallucination rate | High | <5% |
| TTS quality | Mediocre | Near studio |
| Total round-trip time | 15-20s | 6-10s |

## Implementation Phases

### Phase 1: Hardware Setup
- [ ] Install RTX 3090
- [ ] Configure CUDA for multi-GPU
- [ ] Verify both cards recognized by PyTorch/Ollama

### Phase 2: Model Migration
- [ ] Move Whisper + TTS to 3060
- [ ] Load larger base model (22B) on 3090
- [ ] Test inference speeds

### Phase 3: Voice Stack Upgrade
- [ ] Evaluate TTS options (Fish Speech, GPT-SoVITS, etc.)
- [ ] Implement voice switching based on speaker
- [ ] Optimize for real-time performance

### Phase 4: Expert Model Training
- [ ] Collect training data from play sessions
- [ ] Curate and clean dataset
- [ ] Fine-tune 7B model with LoRA
- [ ] Evaluate and iterate

### Phase 5: Model Routing
- [ ] Implement edge case detection
- [ ] Build routing logic between expert/general
- [ ] Test handoff scenarios
- [ ] Optimize for minimal latency

## Notes

- Both LLMs on 3090 for fastest inference (shared memory bus)
- Voice stack isolated on 3060 (no competition for VRAM)
- Expert model stays loaded (fast response for 90% of requests)
- General model stays loaded (no cold-start delay for edge cases)
- ~5GB headroom on each card for safety

## References

- Current engine: `engine/dm_engine_v2.py`
- State management: `engine/state_manager.py`
- Voice services: `services/voice_input.py`, `services/voice_output.py`
