#!/usr/bin/env python3
"""
Parse Flask console logs to extract training examples for fine-tuning.

Extracts:
- Player intent classification
- Target NPC
- Location and NPCs present (from TRAINING_CONTEXT)
- Player input (from TRAINING_INPUT)
- LLM responses with speaker tags
- Quality labels (good/bad/hallucination)

Output: JSON file suitable for LoRA fine-tuning
"""

import re
import json
import sys
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict, field

# Known hallucinated NPCs (for flagging bad examples)
HALLUCINATED_NPCS = [
    'aldern', 'shalelu', 'jorick', 'rockfinder', 'belka',
    'foxglove', 'tsuto', 'nualia', 'orik'  # Common Pathfinder NPCs that might bleed through
]

@dataclass
class TrainingExample:
    """A single training example extracted from logs."""
    timestamp: str
    location: str
    npcs_present: List[str]
    player_input_raw: str
    player_input_cleaned: str
    player_intent: str
    target: Optional[str]
    dm_addressed: bool
    speaker_tag: str
    response_text: str
    quality: str  # 'good', 'bad_tag', 'hallucination', 'needs_review'
    issues: List[str] = field(default_factory=list)
    
    def to_dict(self):
        return asdict(self)


def parse_log_file(filepath: str) -> List[TrainingExample]:
    """Parse a Flask log file and extract training examples."""
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    examples = []
    lines = content.split('\n')
    
    # Patterns for the new TRAINING_* format
    intent_pattern = r'INFO:engine\.dm_engine_v2:Player intent: (\w+), target: (\w+|None), dm_addressed: (True|False)'
    context_pattern = r'INFO:engine\.dm_engine_v2:TRAINING_CONTEXT: location=([^,]+), npcs_present=\[([^\]]*)\]'
    input_pattern = r'INFO:engine\.dm_engine_v2:TRAINING_INPUT: raw="([^"]*)", cleaned="([^"]*)"'
    response_pattern = r'INFO:engine\.dm_engine_v2:Raw response: \[([^\]]+)\] (.+)'
    output_pattern = r'INFO:engine\.dm_engine_v2:TRAINING_OUTPUT: speaker_tag="([^"]*)", response="([^"]*)"'
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Look for player intent (start of a training example)
        intent_match = re.search(intent_pattern, line)
        if intent_match:
            intent = intent_match.group(1)
            target = intent_match.group(2)
            if target == 'None':
                target = None
            dm_addressed = intent_match.group(3) == 'True'
            
            # Initialize with defaults
            location = "unknown"
            npcs_present = []
            player_input_raw = ""
            player_input_cleaned = ""
            speaker_tag = "DM"
            response_text = ""
            
            # Look ahead for the other TRAINING_* lines
            for j in range(i + 1, min(i + 15, len(lines))):
                check_line = lines[j]
                
                # Check for TRAINING_CONTEXT
                context_match = re.search(context_pattern, check_line)
                if context_match:
                    location = context_match.group(1)
                    npcs_str = context_match.group(2)
                    if npcs_str:
                        # Parse the NPC list: 'Ameiko Kaijitsu', 'Guard Captain'
                        npcs_present = [n.strip().strip("'\"") for n in npcs_str.split(',') if n.strip()]
                
                # Check for TRAINING_INPUT
                input_match = re.search(input_pattern, check_line)
                if input_match:
                    player_input_raw = input_match.group(1)
                    player_input_cleaned = input_match.group(2)
                
                # Check for Raw response (has speaker tag)
                response_match = re.search(response_pattern, check_line)
                if response_match:
                    speaker_tag = response_match.group(1)
                
                # Check for TRAINING_OUTPUT (has full response)
                output_match = re.search(output_pattern, check_line)
                if output_match:
                    # speaker_tag from output might be normalized
                    response_text = output_match.group(2)
                    if response_text.endswith('...'):
                        # Response was truncated, try to get from TTS
                        response_text = extract_full_response(lines, j)
                    break
                
                # Stop if we hit another intent (next example)
                if 'Player intent:' in check_line and j > i:
                    break
            
            # If no TRAINING_OUTPUT found, fall back to TTS extraction
            if not response_text:
                response_text = extract_full_response(lines, i + 1)
            
            # Skip system intents
            if intent == 'system':
                i += 1
                continue
            
            # Analyze quality
            quality, issues = analyze_quality(
                intent, target, dm_addressed,
                speaker_tag, response_text, npcs_present
            )
            
            # Extract timestamp
            timestamp = extract_timestamp(lines, i)
            
            example = TrainingExample(
                timestamp=timestamp,
                location=location,
                npcs_present=npcs_present,
                player_input_raw=player_input_raw,
                player_input_cleaned=player_input_cleaned,
                player_intent=intent,
                target=target,
                dm_addressed=dm_addressed,
                speaker_tag=speaker_tag,
                response_text=response_text,
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
                   speaker_tag: str, response: str, npcs_present: List[str]) -> tuple:
    """Analyze response quality and flag issues."""
    
    issues = []
    response_lower = response.lower()
    
    # Check for hallucinated NPCs
    for hallucinated in HALLUCINATED_NPCS:
        if hallucinated in response_lower:
            issues.append(f"hallucinated_npc:{hallucinated}")
    
    # Check if response mentions NPCs not in npcs_present
    if npcs_present:
        # Extract names mentioned in response that look like NPC names (capitalized)
        # This is a heuristic - could be improved
        npc_names_lower = [n.lower() for n in npcs_present]
        npc_first_names = [n.split()[0].lower() for n in npcs_present]
        
        # Common NPC-like patterns in response
        mentioned_pattern = r'"([^"]+)" (?:says|replies|responds|asks|whispers|shouts)'
        
    # Check speaker tag consistency
    if intent == 'dialogue' and target:
        if speaker_tag == 'DM' and not dm_addressed:
            issues.append("dm_tag_for_npc_dialogue")
    
    # Check for story inconsistencies
    story_issues = [
        ('my brother', "story_inconsistency:mentions_brother"),
        ('my sister', "story_inconsistency:mentions_sister"),
        ('my little brother', "story_inconsistency:ameiko_brother"),
        ('my husband', "story_inconsistency:mentions_husband"),
        ('my wife', "story_inconsistency:mentions_wife"),
    ]
    for keyword, issue in story_issues:
        if keyword in response_lower and 'kidnap' in response_lower:
            issues.append(issue)
    
    # Determine overall quality
    if not issues:
        quality = 'good'
    elif any('hallucinated' in i for i in issues):
        quality = 'hallucination'
    elif any('dm_tag_for_npc' in i for i in issues):
        quality = 'bad_tag'
    else:
        quality = 'needs_review'
    
    return quality, issues


def generate_training_format(examples: List[TrainingExample]) -> List[Dict]:
    """Convert examples to fine-tuning format."""
    
    training_data = []
    
    for ex in examples:
        entry = {
            "context": {
                "location": ex.location,
                "npcs_present": ex.npcs_present
            },
            "input": {
                "raw": ex.player_input_raw,
                "cleaned": ex.player_input_cleaned,
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
    print("LOCATIONS:")
    print("-"*60)
    
    locations = {}
    for ex in examples:
        locations[ex.location] = locations.get(ex.location, 0) + 1
    
    for loc, count in sorted(locations.items(), key=lambda x: -x[1]):
        print(f"  {loc}: {count}")
    
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
        print("  python parse_training_logs.py console_log.txt data/training/session_002.json")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else 'training_data.json'
    
    print(f"Parsing: {input_file}")
    
    examples = parse_log_file(input_file)
    print_summary(examples)
    
    training_data = generate_training_format(examples)
    
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
