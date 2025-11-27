import struct
import os

ES = 'utf-8'

class TextType:
    def __init__(self, file_path):
        self.data_path = f"{file_path}_data_text.dat" # almacenará todas las filas del tipo texto de esa columna
        self.lengths_path = f"{file_path}_lengths.dat" # almacenará los sizes
        self.LEN_FORMAT = '<I'           
        self.LEN_SIZE = struct.calcsize(self.LEN_FORMAT)

        if not (os.path.exists(self.data_path)):
            self._initialize()
    
    def _initialize(self):
        with open(self.data_path, "wb"):
            pass
        with open(self.lengths_path, "wb"):
            pass
    
    def read(self, 
             pos: int, 
             length: int
            ) -> str:
        
        f = open(self.data_path, "rb")
        f.seek(pos)
        text = f.read(length).decode(ES)
        f.close()

        return text
    
    def write(self, 
                text: str
              ) -> tuple[int, int]:
        
        f = open(self.data_path, "ab")
        pos = f.tell()
        encoded_text = text.encode(ES)
        length = len(encoded_text)
        f.write(encoded_text)
        f.close()

        f = open(self.lengths_path, "ab")
        f.write(struct.pack(self.LEN_FORMAT, length))
        f.close()

        return (pos, length)
    
    def read_all(self
                ) -> list[str]:
        
        ans = []
        data = open(self.data_path, "rb")
        lens = open(self.lengths_path, "rb")

        while True:
            bin_len = lens.read(self.LEN_SIZE)
            if not bin_len:
                break
            len_ = struct.unpack(self.LEN_FORMAT, bin_len)[0]
            text = data.read(len_).decode(ES)
            ans.append(text)

        data.close()
        lens.close()

        return ans

