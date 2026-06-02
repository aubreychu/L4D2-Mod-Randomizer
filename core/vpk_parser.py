import struct
from core.config import VPK_DICT
from core.models import ModItem

async def extract_vpk_paths(stream_gen) -> list:
    files = []
    try:
        class AsyncBuffer:
            def __init__(self, gen):
                self.gen = gen
                self.buffer = bytearray()
                self.eof = False
                self.bytes_read = 0

            async def read(self, n):
                while len(self.buffer) < n and not self.eof:
                    try:
                        chunk = await self.gen.__anext__()
                        if chunk:
                            self.buffer.extend(chunk)
                    except StopAsyncIteration:
                        self.eof = True
                    except Exception:
                        self.eof = True

                data = self.buffer[:n]
                del self.buffer[:n]
                self.bytes_read += len(data)
                return bytes(data)

            async def read_null_term_string(self):
                result = bytearray()
                while True:
                    idx = self.buffer.find(b'\x00')
                    if idx != -1:
                        result.extend(self.buffer[:idx])
                        del self.buffer[:idx+1]
                        self.bytes_read += len(result) + 1
                        try:
                            return result.decode('utf-8', errors='ignore')
                        except:
                            return ""
                    else:
                        result.extend(self.buffer)
                        self.buffer.clear()
                        if self.eof:
                            self.bytes_read += len(result)
                            break
                        try:
                            chunk = await self.gen.__anext__()
                            if chunk:
                                self.buffer.extend(chunk)
                        except StopAsyncIteration:
                            self.eof = True
                        except Exception:
                            self.eof = True
                try:
                    return result.decode('utf-8', errors='ignore')
                except:
                    return ""

        buf = AsyncBuffer(stream_gen)
        header = await buf.read(12)
        if len(header) < 12: return files
        if struct.unpack_from('<I', header, 0)[0] != 0x55aa1234: return files
        version = struct.unpack_from('<I', header, 4)[0]
        tree_size = struct.unpack_from('<I', header, 8)[0]

        if version == 2:
            extra = await buf.read(16)
            if len(extra) < 16: return files

        header_size = 12 if version == 1 else 28

        while buf.bytes_read < tree_size + header_size:
            ext = await buf.read_null_term_string()
            if not ext: break
            while buf.bytes_read < tree_size + header_size:
                path = await buf.read_null_term_string()
                if not path: break
                while buf.bytes_read < tree_size + header_size:
                    name = await buf.read_null_term_string()
                    if not name: break

                    # read 18 bytes
                    meta = await buf.read(18)
                    if len(meta) < 18: break

                    if ext in {'mdl', 'vmt', 'vtf', 'wav', 'mp3', 'txt', 'pcf'}:
                        files.append(f"{path}/{name}.{ext}")
    except Exception as e:
        pass
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