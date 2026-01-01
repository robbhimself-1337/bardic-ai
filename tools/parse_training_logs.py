#!/usr/bin/env python3
"""
Parse Flask console logs to extract training examples for fine-tuning.

Extracts:
- Player intent classification
- Target NPC
- LLM responses with speaker tags
- Quality labels (good/bad/hallucination)

Output: JSON file suitable for LoRA fine-tuning
"""

import re
import json
import sys
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict

# Known valid NPCs for the goblin_kidnapping_v2 campaign
VALID_NPCS = {
    'ameiko': 'Ameiko Kaijitsu',
    'marcus': 'Guard Captain Marcus Thorne', 
    'tobias': 'Old Man Tobias Greenthorn'
}

# Known hallucinated NPCs (for flagging bad examples)
HALLUCINATED_NPCS = [
    'aldern', 'shalelu', 'jorick', 'rockfinder', 'belka'
]

@dataclass
class TrainingExample:
    """A single training example extracted from logs."""
    timestamp: str
    player_intent: str
    target: Optional[str]
    dm_addressed: bool
    speaker_tag: str
    response_text: str
    quality: str  # 'good', 'bad_tag', 'hallucination', 'unknown'
    issues: List[str]
    
    def to_dict(self):
        return asdict(self)


def parse_log_file(filepath: str) -> List[TrainingExample]:
    """Parse a Flask log file and extract training examples."""
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    examples = []
    
    # Pattern for player intent
    intent_pattern = r'INFO:engine\.dm_engine_v2:Player intent: (\w+), target: (\w+|None), dm_addressed: (True|False)'
    
    # Split into lines for processing
    lines = content.split('\n')
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Look for player intent
        intent_match = re.search(intent_pattern, line)
        if intent_match:
            intent = intent_match.group(1)
            target = intent_match.group(2)
            if target == 'None':
                target = None
            dm_addressed = intent_match.group(3) == 'True'
            
            # Look for raw response on next line
            if i + 1 < len(lines):
                next_line = lines[i + 1]
                response_match = re.search(r'INFO:engine\.dm_engine_v2:Raw response: \[([^\]]+)\] (.+)', next_line)
                
                if response_match:
                    speaker_tag = response_match.group(1)
                    
                    # Get full response from TTS input
                    full_response = extract_full_response(lines, i + 1)
                    
                    # Analyze quality
                    quality, issues = analyze_quality(
                        intent, target, dm_addressed, 
                        speaker_tag, full_response
                    )
                    
                    # Extract timestamp
                    timestamp = extract_timestamp(lines, i)
                    
                    example = TrainingExample(
                        timestamp=timestamp,
                        player_intent=intent,
                        target=target,
                        dm_addressed=dm_addressed,
                        speaker_tag=speaker_tag,
                        response_text=full_response,
                        quality=quality,
                        issues=issues
                    )
                    examples.append(example)
        
        i += 1
    
    return examples


def extract_full_response(lines: List[str], start_idx: int) -> str:
    """Extract full response text from TTS input lines."""
    
    response_parts = []
    
    for i in range(start_idx, min(start_idx + 30, len(lines))):
        line = lines[i]
        
        if 'Player intent:' in line:
            break
            
        tts_match = re.search(r"INFO:TTS\.utils\.synthesizer:Input: \[(.+)\]$", line)
        if tts_match:
            try:
                sentences_str = tts_match.group(1)
                sentences = eval(f"[{sentences_str}]")
                response_parts.extend(sentences)
            except:
                pass
    
    return ' '.join(response_parts)


def extract_timestamp(lines: List[str], idx: int) -> str:
    """Extract timestamp from nearby werkzeug log lines."""
    
    for i in range(idx, max(0, idx - 10), -1):
        ts_match = re.search(r'\[(\d{2}/\w+/\d{4} \d{2}:\d{2}:\d{2})\]', lines[i])
        if ts_match:
            return ts_match.group(1)
    
    return "unknown"


def analyze_quality(intent: str, target: Optional[str], dm_addressed: bool,
                   speaker_tag: str, response: str) -> tuple:
    """Analyze response quality and flag issues."""
    
    issues = []
    response_lower = response.lower()
    
    # Check for hallucinated NPCs
    for hallucinated in HALLUCINATED_NPCS:
        if hallucinated in response_lower:
            issues.append(f"hallucinated_npc:{hallucinated}")
    
    # Check speaker tag consistency
    if intent == 'dialogue' and target:
        expected_npc = VALID_NPCS.get(target)
        if expected_npc and speaker_tag != expected_npc and speaker_tag != 'DM':
            issues.append(f"wrong_speaker_tag:expected={expected_npc},got={speaker_tag}")
        if speaker_tag == 'DM' and not dm_addressed:
            issues.append("dm_tag_for_npc_dialogue")
    
    # Check for story inconsistencies
    story_issues = [
        ('brother', "story_inconsistency:mentions_brother"),
        ('sister', "story_inconsistency:mentions_sister"),
        ('my little brother', "story_inconsistency:ameiko_brother"),
    ]
    for keyword, issue in story_issues:
        if keyword in response_lower and 'kidnap' in response_lower:
            issues.append(issue)
    
    # Determine overall quality
    if not issues:
        quality = 'good'
    elif any('hallucinated' in i for i in issues):
        quality = 'hallucination'
    elif any('wrong_speaker' in i or 'dm_tag_for_npc' in i for i in issues):
        quality = 'bad_tag'
    else:
        quality = 'needs_review'
    
    return quality, issues


def generate_training_format(examples: List[TrainingExample], 
                            campaign_context: Dict) -> List[Dict]:
    """Convert examples to fine-tuning format."""
    
    training_data = []
    
    for ex in examples:
        if ex.player_intent == 'system':
            continue
            
        entry = {
            "context": {
                "location": campaign_context.get('location', 'rusty_dragon_main'),
                "npcs_present": campaign_context.get('npcs', ['ameiko']),
                "valid_npcs": list(VALID_NPCS.values())
            },
            "input": {
                "intent": ex.player_intent,
                "target": ex.target,
                "dm_addressed": ex.dm_addressed
            },
            "output": {
                "speaker_tag": ex.speaker_tag,
                "response": ex.response_text
            },
            "metadata": {
                "quality": ex.quality,
                "issues": ex.issues,
                "timestamp": ex.timestamp
            }
        }
        training_data.append(entry)
    
    return training_data


def print_summary(examples: List[TrainingExample]):
    """Print summary statistics."""
    
    print("\n" + "="*60)
    print("TRAINING DATA EXTRACTION SUMMARY")
    print("="*60)
    
    total = len(examples)
    good = sum(1 for e in examples if e.quality == 'good')
    bad_tag = sum(1 for e in examples if e.quality == 'bad_tag')
    hallucination = sum(1 for e in examples if e.quality == 'hallucination')
    needs_review = sum(1 for e in examples if e.quality == 'needs_review')
    
    print(f"\nTotal examples extracted: {total}")
    print(f"  ✓ Good quality:    {good}")
    print(f"  ✗ Bad speaker tag: {bad_tag}")  
    print(f"  ✗ Hallucination:   {hallucination}")
    print(f"  ? Needs review:    {needs_review}")
    
    print("\n" + "-"*60)
    print("EXAMPLES BY INTENT TYPE:")
    print("-"*60)
    
    intents = {}
    for ex in examples:
        intents[ex.player_intent] = intents.get(ex.player_intent, 0) + 1
    
    for intent, count in sorted(intents.items()):
        print(f"  {intent}: {count}")
    
    print("\n" + "-"*60)
    print("ISSUES FOUND:")
    print("-"*60)
    
    all_issues = []
    for ex in examples:
        all_issues.extend(ex.issues)
    
    issue_counts = {}
    for issue in all_issues:
        issue_counts[issue] = issue_counts.get(issue, 0) + 1
    
    if issue_counts:
        for issue, count in sorted(issue_counts.items(), key=lambda x: -x[1]):
            print(f"  {issue}: {count}")
    else:
        print("  None")
    
    print("\n")


def main():
    if len(sys.argv) < 2:
        print("Usage: python parse_training_logs.py <logfile> [output.json]")
        print("\nExample:")
        print("  python parse_training_logs.py trainingmaterial.txt training_data.json")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else 'training_data.json'
    
    print(f"Parsing: {input_file}")
    
    examples = parse_log_file(input_file)
    print_summary(examples)
    
    campaign_context = {
        'location': 'rusty_dragon_main',
        'npcs': ['ameiko']
    }
    training_data = generate_training_format(examples, campaign_context)
    
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(training_data, f, indent=2)
    
    print(f"Training data saved to: {output_path}")
    print(f"Total usable examples: {len(training_data)}")
    
    raw_output = output_path.parent / (output_path.stem + '_raw.json')
    with open(raw_output, 'w') as f:
        json.dump([e.to_dict() for e in examples], f, indent=2)
    
    print(f"Raw examples saved to: {raw_output}")


if __name__ == '__main__':
    main()
