"""
Text Chunking Service.
Splits documents into overlapping chunks on sentence boundaries.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class Chunk:
    text: str
    start_char: int
    end_char: int
    chunk_index: int
    page_number: Optional[int] = None

class ChunkingService:
    def chunk_text(self, text: str, chunk_size: int = 512, chunk_overlap: int = 64) -> List[Chunk]:
        """
        Splits text into chunks, respecting sentence boundaries where possible.
        chunk_size and chunk_overlap are roughly word counts, but here implemented
        as character limits for simplicity (chunk_size * 5 roughly equals char length).
        
        Using average 5 chars per word:
        char_size = chunk_size * 5
        char_overlap = chunk_overlap * 5
        """
        char_size = chunk_size * 5
        char_overlap = chunk_overlap * 5
        
        # Simple sentence tokenizer regex
        sentences = []
        for match in re.finditer(r'[^.!?\n]+[.!?\n]+|\s*$', text):
            s = match.group(0)
            if s.strip():
                sentences.append((s, match.start(), match.end()))
                
        chunks = []
        current_chunk_sentences = []
        current_length = 0
        current_start = 0
        chunk_index = 0
        
        def commit_chunk(sentences_tuple, idx):
            if not sentences_tuple:
                return None
            chunk_text = "".join(s[0] for s in sentences_tuple).strip()
            if not chunk_text:
                return None
            start = sentences_tuple[0][1]
            end = sentences_tuple[-1][2]
            return Chunk(text=chunk_text, start_char=start, end_char=end, chunk_index=idx)
        
        for s_text, s_start, s_end in sentences:
            s_len = len(s_text)
            
            # If a single sentence is larger than char_size, we just add it anyway 
            # (or we could hard split, but keeping sentence intact is better)
            
            if current_length + s_len > char_size and current_chunk_sentences:
                # Commit current chunk
                chunk = commit_chunk(current_chunk_sentences, chunk_index)
                if chunk:
                    chunks.append(chunk)
                    chunk_index += 1
                
                # Overlap logic: keep sentences from the end of current_chunk_sentences
                # until they fit in char_overlap
                overlap_len = 0
                overlap_sentences = []
                for prev_s in reversed(current_chunk_sentences):
                    if overlap_len + len(prev_s[0]) <= char_overlap:
                        overlap_sentences.insert(0, prev_s)
                        overlap_len += len(prev_s[0])
                    else:
                        break
                
                current_chunk_sentences = overlap_sentences
                current_chunk_sentences.append((s_text, s_start, s_end))
                current_length = sum(len(x[0]) for x in current_chunk_sentences)
            else:
                current_chunk_sentences.append((s_text, s_start, s_end))
                current_length += s_len
                
        if current_chunk_sentences:
            chunk = commit_chunk(current_chunk_sentences, chunk_index)
            if chunk:
                chunks.append(chunk)
                
        return chunks

chunking_service = ChunkingService()
