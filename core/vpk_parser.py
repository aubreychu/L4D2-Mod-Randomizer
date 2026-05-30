import struct
from core.config import VPK_DICT
from core.models import ModItem

def read_null_term_string(data: bytes, offset: int):
    end = data.find(b'\x00', offset)
    if end == -1 or end == offset: return "", offset + 1
    try: return data[offset:end].decode('utf-8', errors='ignore'), end + 1
    except: return "", end + 1

def extract_vpk_paths(data: bytes) -> list:
    files = []
    try:
        if struct.unpack_from('<I', data, 0)[0] != 0x55aa1234: return files
        version = struct.unpack_from('<I', data, 4)[0]
        tree_size = struct.unpack_from('<I', data, 8)[0]
        offset = 12 if version == 1 else 28

        while offset < len(data) and offset < tree_size + (12 if version == 1 else 28):
            ext, offset = read_null_term_string(data, offset)
            if not ext: break
            while offset < len(data):
                path, offset = read_null_term_string(data, offset)
                if not path: break
                while offset < len(data):
                    name, offset = read_null_term_string(data, offset)
                    if not name: break
                    offset += 18 
                    if ext in ['mdl', 'vmt', 'vtf', 'wav', 'mp3', 'txt', 'pcf']:
                        files.append(f"{path}/{name}.{ext}")
    except: pass 
    return files

def map_extracted_files_to_slots(mod: ModItem, internal_files: list):
    found_models = set()
    found_audios = set()
    
    # Save the raw paths for the Visual Inspector
    mod.eval.raw_paths = internal_files
    
    for file_path in internal_files:
        file_path_lower = file_path.lower()
        for slot_name, expected_paths in VPK_DICT.items():
            for expected in expected_paths:
                if expected.lower() in file_path_lower:
                    if file_path_lower.endswith(('.mdl', '.vmt', '.vtf', '.pcf')): 
                        found_models.add(slot_name)
                    elif file_path_lower.endswith(('.wav', '.mp3')): 
                        found_audios.add(slot_name)
                        
    mod.eval.model_slots = list(found_models)
    mod.eval.audio_slots = list(found_audios)