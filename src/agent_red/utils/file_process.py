from typing import List, Callable
import json
from ..custom_types import MemoryDataset, Sample, ChatMessage, ChatMessageUser, ChatMessageAssistant


def get_conversation_format(raw_content: str) -> List[ChatMessage]:
    """
    Parse raw conversation content into a list of ChatMessages.
    
    Args:
        raw_content: Raw string content containing conversation
        
    Returns:
        List of ChatMessage objects representing the conversation
    """
    messages = []
    
    # Split content by the separators we see in the file
    parts = raw_content.split('---')
    
    for part in parts:
        part = part.strip()
        if not part:
            continue
            
        # Check if this part contains a user message
        if '**User:**' in part:
            # Extract content after the User marker
            if '\n\n' in part:
                content = '\n\n'.join(part.split('\n\n')[1:])  # Skip the first part with the User marker
            else:
                content = part.replace('**User:**', '').strip()
            messages.append(ChatMessageUser(content=content))
            
        # Check if this part contains an assistant message
        elif '**Assistant:**' in part:
            # Extract content after the Assistant marker
            if '\n\n' in part:
                content = '\n\n'.join(part.split('\n\n')[1:])  # Skip the first part with the Assistant marker
            else:
                content = part.replace('**Assistant:**', '').strip()
            messages.append(ChatMessageAssistant(content=content))
                
    return messages


def jsonl_dataset(file_path: str, dataset_transform: Callable | None = None) -> MemoryDataset:
    data = []
    with open(file_path, 'r') as f:
        for line in f:
            data.append(json.loads(line))
    if dataset_transform is None:
        dataset_transform = lambda a: a
    samples = [dataset_transform(Sample(
        user_instruction=sample.get('input', ''),
        id=sample.get('id', ''),
        metadata=sample.get('metadata', {}),
        category=sample.get("category", ""),
        subcategory=sample.get("subcategory", "")
    )) for sample in data]
    return MemoryDataset(samples)