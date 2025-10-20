import struct
from typing import List


class DynamicRecord:
    def __init__(self, table_schema: List, **valores):
        self.schema = table_schema
        self.FORMAT = self._build_format(table_schema)
        self.SIZE_OF_RECORD = struct.calcsize(self.FORMAT)

        for col in table_schema:
            if col.name not in valores:
                raise ValueError(f"Campo requerido faltante: '{col.name}'")

            value = valores[col.name]
            
            if col.data_type.value == "INT" or col.data_type.value == "BIGINT":
                tranfor_valor = int(value)
        
            elif col.data_type.value == "FLOAT":
                tranfor_valor = float(value)

            elif col.data_type.value == "VARCHAR":
                tranfor_valor = str(value)

            elif col.data_type.value == "DATE":
                tranfor_valor = str(value)
            
            elif col.data_type.value == "ARRAY":
                if not isinstance(value, (list, tuple)):
                    raise ValueError(f"'{col.name}' debe ser array")
                
                if len(value) != col.array_dimensions:
                    raise ValueError(
                        f"Array '{col.name}' requiere {col.array_dimensions} elementos, "
                        f"recibió {len(value)}"
                    )
                
                if col.element_type.value == "FLOAT":
                    tranfor_valor = [float(x) for x in value]
                elif col.element_type.value == "INT":
                    tranfor_valor = [int(x) for x in value]
                else:
                    tranfor_valor = list(value)


            setattr(self, col.name, tranfor_valor)

        self.deleted = valores.get('deleted', False)
    
    @staticmethod
    def _build_format(table_schema: List) -> str:
        format_parts = []

        for col in table_schema:
            if col.data_type.value == "INT":
                format_parts.append("i")
            elif col.data_type.value == "BIGINT":
                format_parts.append("q")  # int64 (long long)
            elif col.data_type.value == "FLOAT":
                format_parts.append("f")
            elif col.data_type.value == "VARCHAR":
                format_parts.append(f"{col.size}s")
            elif col.data_type.value == "DATE":
                format_parts.append("10s")  # YYYY-MM-DD
            elif col.data_type.value == "ARRAY":
                if col.element_type.value == "FLOAT":
                    format_parts.append(f"{col.array_dimensions}f")
                elif col.element_type.value == "INT":
                    format_parts.append(f"{col.array_dimensions}i")
                else:
                    raise ValueError(f"Tipo de array no soportado: {col.element_type}")
        
        format_parts.append("?") 
        return "".join(format_parts)
    
    def pack(self) -> bytes:
        pack_values = []
        
        for col in self.schema:
            value = getattr(self, col.name)
            
            if col.data_type.value == "VARCHAR":
                encoded = value[:col.size].ljust(col.size).encode('utf-8', errors='replace')
                pack_values.append(encoded)
            elif col.data_type.value == "DATE":
                encoded = value[:10].ljust(10).encode('utf-8', errors='replace')
                pack_values.append(encoded)
            elif col.data_type.value == "ARRAY":
                pack_values.extend(value)
            else:
                pack_values.append(value)
        
        pack_values.append(self.deleted)
        return struct.pack(self.FORMAT, *pack_values)
    
    @classmethod
    def unpack(cls, table_schema: List, data: bytes):
        format_string = cls._build_format(table_schema)
        unpacked = struct.unpack(format_string, data)

        valores = {}
        value_index = 0
        
        for col in table_schema:
            if col.data_type.value == "VARCHAR":
                valores[col.name] = unpacked[value_index].decode('utf-8', errors='replace').rstrip()
                value_index += 1
            elif col.data_type.value == "DATE":
                valores[col.name] = unpacked[value_index].decode('utf-8', errors='replace').rstrip()
                value_index += 1
            elif col.data_type.value == "ARRAY":
                array_values = []
                for _ in range(col.array_dimensions):
                    array_values.append(unpacked[value_index])
                    value_index += 1
                valores[col.name] = array_values
            else:
                valores[col.name] = unpacked[value_index]
                value_index += 1

        valores['deleted'] = unpacked[-1]

        return cls(table_schema, **valores)
    
    def __str__(self):
        parts = []
        for col in self.schema:
            value = getattr(self, col.name)
            parts.append(f"{col.name}: {value}")
        
        status = "(DEL)" if self.deleted else ""
        return f"{', '.join(parts)} {status}"