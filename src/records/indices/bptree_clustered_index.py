from __future__ import annotations
import os
import struct
import math
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from .base_index import BaseIndex
from ..record import DynamicRecord
from ...parser.ast import ColumnDef
from .page_btree_clustered import Page, Int64Codec, FixedStrCodec


def calcular_M(expected_records: Optional[int] = None) -> int:
    if expected_records is None:
        return 128 
    optimal = int(2 * math.sqrt(expected_records))

    power_of_2 = 2 ** round(math.log2(optimal))

    return max(64, min(1024, power_of_2))

@dataclass
class ExtractionResult():
    key: Any = None 
    right_tree: Optional[int] = -1
    left_tree: Optional[int] = -1

class BTreeIndex(BaseIndex):

    def __init__(self, 
                 column_name: str,        # supposed to be Id 
                 table_schema: List[ColumnDef],
                 filename: str = None, 
                 is_primary: bool = True, # true always bc is clustered
                 primary_key_column: str = None,
                 M: int = None,
                 expected_records: Optional[int] = None
                 ):
        if M is None:
            M = calcular_M(expected_records)
        
        if M < 3:
            raise ValueError("M must be greater than 2")

        super().__init__(column_name, filename, is_primary, primary_key_column)

        self.io_stats = {
            'disk_reads': 0,
            'disk_writes': 0,
            'node_reads': 0,
            'node_writes': 0
        }

        col = next((c for c in table_schema if c.name == column_name), None)

        if col is None:
            raise ValueError(f"Columna '{column_name}' no existe en el schema")

        dt = col.data_type.value.upper()

        if dt == "INT":
            self.key_codec = Int64Codec()
        elif dt == "VARCHAR":
            self.key_codec = FixedStrCodec(size=20)
        else:
            raise ValueError(f"type not supported: {type}")
        
        self.table_schema = table_schema
        temp_record = DynamicRecord._build_format(table_schema)
        self.RECORD_SIZE = struct.calcsize(temp_record)

        self.root_page = -1
        self.M: int = M

        self.page_size = Page.page_size(
            block_factor=self.M, 
            key_codec=self.key_codec,
            record_size=self.RECORD_SIZE
            )

        if os.path.exists(self.filename) and os.path.getsize(self.filename) > 0:
            self.root_page = 0
    
    def reset_io_stats(self):
        """Resetear contadores de I/O"""
        self.io_stats = {
            'disk_reads': 0,
            'disk_writes': 0,
            'node_reads': 0,
            'node_writes': 0
        }
    
    def get_io_stats(self) -> Dict[str, int]:
        """Obtener estadísticas de I/O actuales"""
        return self.io_stats.copy()

    def search(self, key: Any) -> List[Dict[str, Any]]:
        """
            Igualdad sobre índice clustered (sin duplicados).
            Devuelve: [{"primary_key": pk}] o [] si no existe.
        """
        out: List[Dict[str, Any]] = []

        pid = getattr(self, "root_page", None)
        if pid is None or pid < 0:
            return out

        # place in leafs
        while True:
            node = self._get_page_by_id(pid)
            if node.is_leaf:
                break
            i = self._lower_bound(node.keys, node.count, key)
            child_pid = node.children[i]
            if child_pid is None or child_pid < 0:
                return out
            pid = child_pid

        i = self._lower_bound(node.keys, node.count, key)

        if i < node.count and node.keys[i] == key:
            rec = node.records[i] if i < len(node.records) else None
            if rec is not None and not getattr(rec, "deleted", False):
                out.append({col.name: getattr(rec, col.name) for col in rec.schema})

            else:
                pass

        return out

    def rangeSearch(self, begin_key: Any, end_key: Any) -> List[Dict[str, Any]]:
        """
            Rango [begin_key, end_key] sobre índice clustered.
            Devuelve: [{"primary_key": pk}, ...] en orden ascendente por clave.
        """
        out: List[Dict[str, Any]] = []

        pid = getattr(self, "root_page", None)
        if pid is None or pid < 0:
            return out

        lo, hi = (begin_key, end_key) if begin_key <= end_key else (end_key, begin_key)

        # desciende hasta la hoja que contendría 'lo'
        while True:
            node = self._get_page_by_id(pid)
            if node.is_leaf:
                break
            i = self._lower_bound(node.keys, node.count, lo)
            child_pid = node.children[i]
            if child_pid is None or child_pid < 0:
                return out
            pid = child_pid

        # posición inicial en la hoja
        i = self._lower_bound(node.keys, node.count, lo)

        leaf_count = 0
        visited_leaves = set()
        current_pid = pid
        
        while True:
            if current_pid in visited_leaves:
                break
            visited_leaves.add(current_pid)
            
            leaf_count += 1

            while i < node.count:
                k = node.keys[i]
                if k is None:
                    i += 1
                    continue
                if k > hi:
                    return out

                rec = node.records[i] if i < len(node.records) else None
                if rec is not None and not getattr(rec, "deleted", False):
                    out.append({col.name: getattr(rec, col.name) for col in rec.schema})
                i += 1

            if node.next_page is None or node.next_page == -1:
                break
            current_pid = node.next_page
            node = self._get_page_by_id(current_pid)
            i = 0

        return out

    def add(self, record: Dict[str, Any]) -> bool:
        key = record[self.column_name]

        dynamic_record = DynamicRecord(self.table_schema, **record)

        if not os.path.exists(self.filename):
            self.io_stats['disk_writes'] += 1 
            self.io_stats['node_writes'] += 1
            with open(self.filename, 'wb') as file:
                root_page = Page(
                    block_factor=self.M,
                    key_codec=self.key_codec,
                    is_leaf=True,
                    record_size=self.RECORD_SIZE # 9
                    )
                root_page.keys[0] = key
                root_page.count = 1
                root_page.records[0] = dynamic_record
                file.write(root_page.pack())
            self.root_page = 0
            return True

        split_result = self._insert(
            id=self.root_page,
            key=key,
            record=dynamic_record
            )

        if split_result is not None:
            parent = Page(
                block_factor=self.M,
                key_codec=self.key_codec,
                is_leaf=False,
                record_size=self.RECORD_SIZE
                )
            parent.keys[0] = split_result.key
            parent.children[0] = self.root_page
            parent.children[1] = split_result.right_tree
            parent.count = 1
            self.root_page = self._append_page(parent)

        return True
    
    def remove(self, key: Any) -> bool:
        
        if self.root_page == -1:
            return True

        self._remove(self.root_page, key)

        root = self._get_page_by_id(self.root_page)

        if root and root.count == 0:
            self.root_page = root.children[0]
            if self.root_page == -1:
                return True
            root = self._get_page_by_id(self.root_page)
            if root.count == 0:
                self.root_page = -1

        return True

    def bulk_load(self, records: List[Dict[str, Any]]) -> bool:
        if not records:
            return True

        valid_records = [r for r in records if self.column_name in r]

        if not valid_records:
            return False

        # ordenamos los registros por clave
        sorted_records = sorted(valid_records, key=lambda x: x[self.column_name])

        # Transformamos a un record dinámico
        dynamic_records = [DynamicRecord(self.table_schema, **rec) for rec in sorted_records]

        if os.path.exists(self.filename):
            os.remove(self.filename)

        leaf_pages = []
        records_per_leaf = self.M - 1 
        
        # Creamos nodos hoja que almacenan los registros, considerando que por hoja puede haber
        # hasta M-1 registros (claves + registros)
        for i in range(0, len(dynamic_records), records_per_leaf):
            batch = dynamic_records[i:i + records_per_leaf]
            
            leaf = Page(
                block_factor=self.M,
                key_codec=self.key_codec,
                is_leaf=True,
                record_size=self.RECORD_SIZE
            )
            
            for j, rec in enumerate(batch):
                leaf.keys[j] = rec.__dict__[self.column_name]
                leaf.records[j] = rec
            
            leaf.count = len(batch)
            leaf_pages.append(leaf)
        
        # cada una de las hojas las unimos (mejora para rango)
        for i in range(len(leaf_pages) - 1):
            leaf_pages[i].next_page = i + 1

        if leaf_pages:
            leaf_pages[-1].next_page = -1

        # Escribimos las hojas en disco
        for page in leaf_pages:
            self._append_page(page)

        # If only one leaf, it's the root
        if len(leaf_pages) == 1:
            self.root_page = 0
            return True

        # Construimos los nodos internos hacia arriba
        current_level = list(range(len(leaf_pages)))
        
        while len(current_level) > 1:
            next_level = []
            keys_per_internal = self.M - 1
            
            for i in range(0, len(current_level), keys_per_internal + 1):
                # del nivel en el que estemos tomamos un batch de hijos
                children_batch = current_level[i:i + keys_per_internal + 1]
                
                internal = Page(
                    block_factor=self.M,
                    key_codec=self.key_codec,
                    is_leaf=False,
                    record_size=self.RECORD_SIZE
                )
                
                # Definimos los hijos utilizando los IDs de página
                for j, child_id in enumerate(children_batch):
                    internal.children[j] = child_id
                
                # Definimos las claves del nodo interno
                for j in range(1, len(children_batch)):
                    child_page = self._get_page_by_id(children_batch[j])
                    internal.keys[j - 1] = child_page.keys[0]
                
                internal.count = len(children_batch) - 1
                
                # Escribimos el nodo interno en disco 
                internal_id = self._append_page(internal)
                next_level.append(internal_id)
            
            current_level = next_level

        # El ultimo nodo q queda es la raíz
        self.root_page = current_level[0]

        return True

    def getAllRecords(self) -> List[Dict[str, Any]]:
        """
            Retorna todos los registros almacenados en el índice
            en orden ascendente por clave. Recorre hojas usando next_page.
        """
        out: List[Dict[str, Any]] = []

        pid = getattr(self, "root_page", None)
        if pid is None or pid < 0 or self._page_count() == 0:
            return out

        while True:
            node = self._get_page_by_id(pid)
            if node.is_leaf:
                break
            if not node.children or node.children[0] is None or node.children[0] < 0:
                return out
            pid = node.children[0]

        while pid != -1:
            leaf = self._get_page_by_id(pid)
            for j in range(leaf.count):
                rec = leaf.records[j] if j < len(leaf.records) else None
                if rec is None:
                    continue
                if getattr(rec, "deleted", False):
                    continue
                out.append({col.name: getattr(rec, col.name) for col in rec.schema})
            pid = leaf.next_page if leaf.next_page is not None else -1

        return out

    def clear_all(self) -> int:
        """
            Elimina todo el índice en disco y resetea el estado en memoria.
            Devuelve la cantidad de registros no borrados que había (estimado).
        """
        import os
        total = 0

        if os.path.exists(self.filename) and os.path.getsize(self.filename) > 0:
            ps = self.page_size
            try:
                with open(self.filename, "rb") as f:
                    n_pages = os.path.getsize(self.filename) // ps
                    self.io_stats['disk_reads'] += n_pages
                    self.io_stats['node_reads'] += n_pages
                    for pid in range(n_pages):
                        f.seek(pid * ps)
                        data = f.read(ps)
                        page = Page.unpack(
                            data=data,
                            key_codec=self.key_codec,
                            BLOCK_FACTOR=self.M,
                            RECORD_SIZE=self.record_size,
                            table_schema=self.table_schema,
                        )
                        if page.is_leaf:
                            for j in range(page.count):
                                rec = page.records[j] if j < len(page.records) else None
                                if rec is not None and not getattr(rec, "deleted", False):
                                    total += 1
            except Exception:
                total = 0
            try:
                os.remove(self.filename)
            except FileNotFoundError:
                pass

        self.root_page = -1
        return total
    
    def display_pretty(self) -> None:
        
        if self._page_count() == 0 or self.root_page == -1:
            print("(árbol vacío)")
            return
        
        self._display_tree(self.root_page, indent="", last=True)

    def display_range(self,
                    lo: Any,
                    hi: Any,
                    inclusive: tuple[bool, bool] = (True, True),
                    show_pid: bool = True,
                    show_idx: bool = False) -> None:
        if self._page_count() == 0 or self.root_page == -1:
            print("(árbol vacío)")
            return

        if lo is None or hi is None:
            print("(rango inválido: lo/hi es None)")
            return

        if lo > hi:
            lo, hi = hi, lo

        start_pid = self._find_leaf_for(lo)
        if start_pid == -1:
            print("(no se encontró hoja inicial)")
            return

        printed = 0
        pid = start_pid
        left_inc, right_inc = inclusive

        while pid != -1:
            page = self._get_page_by_id(pid)
            for j in range(page.count):
                k = page.keys[j]

                # bordes del rango
                if k < lo or (k == lo and not left_inc):
                    continue
                if k > hi or (k == hi and not right_inc):
                    pid = -1
                    break

                rec = None
                if j < len(page.records):
                    rec = page.records[j]  # DynamicRecord o None

                # construir metadatos opcionales
                meta = []
                if show_pid:
                    meta.append(f"pid={pid}")
                if show_idx:
                    meta.append(f"idx={j}")
                meta_str = f" ({', '.join(meta)})" if meta else ""

                # qué mostrar del record
                if rec is None:
                    print(f"{k}{meta_str}")
                else:
                    # si tienes primary_key_column configurado, muéstralo
                    pk_str = None
                    if getattr(self, "primary_key_column", None):
                        pk_name = self.primary_key_column
                        pk_str = getattr(rec, pk_name, None)
                    if pk_str is not None:
                        print(f"{k} -> {pk_str}{meta_str}")
                    else:
                        # fallback: imprime todas las columnas del DynamicRecord
                        cols = []
                        for col in rec.schema:
                            cols.append(f"{col.name}={getattr(rec, col.name)}")
                        print(f"{k} -> {{ {', '.join(cols)} }}{meta_str}")

                printed += 1

            if pid != -1:
                pid = page.next_page

        if printed == 0:
            print("(sin resultados en el rango)")

    # ---------------------------------
    # ||            UTILS            ||
    # ---------------------------------

    def _insert(self, 
                id: int, # id of page in index.dat
                key: Any, # PK
                record: DynamicRecord 
                ) -> Optional[ExtractionResult]:
        
        node = self._get_page_by_id(id)

        i = 0
        while i < node.count and key > node.keys[i]:
            i += 1

        if i < node.count and node.keys[i] == key:
            return None
        
        if node.is_leaf:
            if node.count < self.M - 1:
                self._relocate(node, key, record)
                self._set_page_by_id(node, id)
            elif ( self.M % 2 == 0 ):
                return self._split_par(node=node, key=key, id=id, record=record)
            else:
                return self._split_impar(node=node, key=key, id=id, record=record)
        else:
            split_result = self._insert(id=node.children[i], key=key, record=record)
            if split_result is not None:
                if node.count < self.M - 1:
                    self._relocate_right(node=node, key=split_result.key, record=record, right_tree=split_result.right_tree)
                    self._set_page_by_id(node, id)
                elif self.M % 2 == 0:
                    return self._split_par(node=node, key=split_result.key, id=id, record=record, right_tree=split_result.right_tree)
                else:
                    return self._split_impar(node=node, key=split_result.key, id=id, record=record, right_tree=split_result.right_tree)
        
        return None
    
    def _split_par(self, 
                   node: Page, 
                   key: Any, 
                   id: int, # reference in index.dat
                   record: DynamicRecord,
                   right_tree: Optional[int] = -1,
                   ) -> ExtractionResult[Any]:
        
        m = (self.M - 1) // 2
        middle = node.keys[m]
        right_node = self._generate_right_node(node, m + 1)
        node.count = m 

        if ( key < middle ):
            if ( node.is_leaf ):
                if ( key < node.keys[m - 1] ):
                    middle = node.keys[m - 1]
                else:
                    middle = key
                right_node = self._generate_right_node(node, m)
            self._relocate_right(node=node, key=key, record=record, right_tree=right_tree)
        else:
            if ( node.is_leaf ):
                node.count += 1
                self._relocate_right(node=right_node, key=key, record=record, right_tree=right_tree)
            else:
                if key < node.keys[m + 1]:
                    middle = key
                    node.count += 1
                    right_node.children[0] = right_tree
                else:
                    middle = node.keys[m + 1]
                    m = m + 1 if ( node.is_leaf ) else m + 2
                    right_node = self._generate_right_node(node, m)
                    node.count = node.count if node.is_leaf else node.count +1
                    self._relocate_right(node=right_node, key= key, record=record, right_tree=right_tree)

        right_node.next_page = node.next_page
        new_id_right_node = self._set_page_by_id(right_node, self._page_count())
        node.next_page = new_id_right_node
        self._set_page_by_id(node, id)
        
        return ExtractionResult(key=middle, left_tree=-1, right_tree=new_id_right_node)

    def _split_impar(self, 
                     node: Page, 
                     key: Any, 
                     id: int,
                     record: DynamicRecord,
                     right_tree: Optional[int] = None
                     ) -> ExtractionResult:
        
        m = (self.M - 1) // 2
        if key > node.keys[m]:
            right_node = self._generate_right_node(node, m + 1)
            middle = node.keys[m]
            node.count = (m + 1) if node.is_leaf else m
            self._relocate_right(right_node, key, right_tree)
        else:
            m = m - 1
            right_node = self._generate_right_node(node, m + 1)
            if key < node.keys[m]:
                middle = node.keys[m]
                node.count = (m + 1) if node.is_leaf else m
                self._relocate_right(node, key, right_tree)
            else:
                middle = key
                if node.is_leaf:
                    node.keys[m + 1] = middle  # incluir en hojas (B+)
                node.count = (m + 2) if node.is_leaf else (m + 1)
                right_node.children[0] = right_tree

        right_node.next = node.next
        node.next = right_node

        return ExtractionResult(middle, None, right_node)

    def _generate_right_node(self, 
                             node: Page, 
                             start_from: int
                             ) -> Page:
        
        right_node = Page(
            block_factor=self.M, 
            key_codec=self.key_codec, 
            is_leaf=node.is_leaf,
            record_size=self.RECORD_SIZE
            )
        i, j = start_from, 0
        while i < self.M - 1:
            right_node.keys[j] = node.keys[i]
            right_node.children[j] = node.children[i] 
            right_node.records[j] = node.records[i] 
            i += 1
            j += 1       
        right_node.children[j] = node.children[i]
        right_node.count = j

        return right_node

    def _relocate(self, 
                  node: Page, 
                  key: Any, 
                  record: DynamicRecord
                  ) -> None:
        
        i = node.count - 1
        while ( i >= 0 and key < node.keys[i] ):
            node.keys[i + 1] = node.keys[i]
            node.records[i + 1] = node.records[i]
            i -= 1
        i += 1
        node.keys[i] = key
        node.records[i] = record
        node.count += 1

    def _relocate_right(self, 
                        node: Page, 
                        key: Any, 
                        record: Optional[DynamicRecord] = None,
                        right_tree: int = -1,
                        ) -> None:
        
        i = node.count - 1
        
        while i >= 0 and key < node.keys[i]:
            node.keys[i + 1] = node.keys[i]
            node.children[i + 2] = node.children[i + 1]
            node.records[i + 1] = node.records[i]
            i -= 1

        i += 1
        node.keys[i] = key
        node.children[i + 1] = right_tree
        node.records[i] = record
        node.count += 1
        
    def _get_page_by_id(self, pid: int) -> Page:
        self.io_stats['disk_reads'] += 1 
        self.io_stats['node_reads'] += 1 
        ps = self.page_size
        with open(self.filename, "rb") as f:
            f.seek(pid * ps)
            data = f.read(ps)
        if len(data) != ps:
            raise EOFError(f"incomplete page: pid={pid}, got={len(data)}, expected={ps}")
        return Page.unpack(
            data, 
            key_codec=self.key_codec, 
            BLOCK_FACTOR=self.M,
            RECORD_SIZE=self.RECORD_SIZE,
            table_schema=self.table_schema
            )

    def _set_page_by_id(self, page: Page, pid: int) -> int:
        self.io_stats['disk_writes'] += 1
        self.io_stats['node_writes'] += 1
        blob = page.pack()
        mode = 'r+b' if os.path.exists(self.filename) else 'wb'
        with open(self.filename, mode) as f:
            f.seek(pid * self.page_size)
            f.write(blob)
        return pid
    
    def _page_count(self) -> int:
        try:
            return os.path.getsize(self.filename) // self.page_size
        except FileNotFoundError:
            return 0

    def _append_page(self, page: Page) -> int:
        pid = self._page_count()
        return self._set_page_by_id(page, pid)

    def _canon(self, v):
        return self.key_codec.from_bin(self.key_codec.to_bin(v))

    def _display_tree(self, pid: int, indent: str, last: bool) -> None:
        page = self._get_page_by_id(pid)
        branch = "└" if last else "├"
        keys_str = ",".join(str(k) for k in page.keys[:page.count])
        tag = " L" if page.is_leaf else ""
        print(f"{indent}{branch}[{keys_str}]{tag} (pid={pid})")

        if not page.is_leaf:
            child_indent = indent + ("  " if last else "│ ")
            child_ids = page.children[:page.count + 1]
            for i, cid in enumerate(child_ids):
                if cid == -1:
                    continue
                self._display_tree(cid, child_indent, last=(i == len(child_ids) - 1))

    def display_levels(self) -> None:
        if self._page_count() == 0:
            print("(árbol vacío)")
            return

        from collections import deque
        q = deque([(self.root_page, 0)])
        cur_level = 0
        line = []

        def flush(level):
            if line:
                print(f"Nivel {level}: " + "   ||   ".join(line))

        while q:
            pid, level = q.popleft()
            if level != cur_level:
                flush(cur_level)
                line = []
                cur_level = level

            page = self._get_page_by_id(pid)
            keys_str = ",".join(str(k) for k in page.keys[:page.count])
            node_tag = "L" if page.is_leaf else "I"
            line.append(f"({node_tag}, pid={pid})[{keys_str}]")

            if not page.is_leaf:
                for cid in page.children[:page.count + 1]:
                    if cid != -1:
                        q.append((cid, level + 1))

        flush(cur_level)

    def _remove(self, 
                id: int, 
                key: Any
                ) -> None:

        node = self._get_page_by_id(id)

        i = 0
        while i < node.count and key > node.keys[i]:
            i += 1

        if node.is_leaf:
            if i < node.count and node.keys[i] == key:
                self._pop_element(node, i)
                self._set_page_by_id(node, id)
            return

        self._remove(node.children[i], key)

        left_id  = node.children[i-1] if i > 0 else -1
        cur_id   = node.children[i]
        right_id = node.children[i+1] if i < node.count else -1

        nc_iminus = self._get_page_by_id(left_id)  if left_id  != -1 else None
        nc_i      = self._get_page_by_id(cur_id)   if cur_id   != -1 else None
        nc_iplus  = self._get_page_by_id(right_id) if right_id != -1 else None

        if nc_i.count < (self.M - 1) // 2:
            # rotación con izquierdo
            if i > 0 and nc_iminus.count > (self.M - 1) // 2:
                if nc_iminus.is_leaf:
                    self._pop_element(nc_iminus, nc_iminus.count - 1)
                    self._set_page_by_id(nc_iminus, left_id)
                # falta verificar si despues del pop queda vacio
                extract_result = self._extract_last(nc_iminus)
                self._relocate_left(node=nc_i, key=node.keys[i - 1], left_tree=extract_result.right_tree)
                node.keys[i - 1] = extract_result.key

                self._set_page_by_id(node, id)
                self._set_page_by_id(nc_i, cur_id)
            # rotación con derecho
            elif i < node.count and nc_iplus.count > (self.M - 1) // 2:
                extract_result = self._extract_first(nc_iplus)
                
                if (nc_i.is_leaf):
                    self._relocate_right(nc_i, extract_result.key, node.records[i], right_tree=extract_result.left_tree)
                else:
                    self._relocate_right(nc_i, node.keys[i], node.records[i], right_tree=extract_result.left_tree)
                node.keys[i] = extract_result.key
                if not node.is_leaf and not nc_i.is_leaf:
                    for idx in range(len(nc_i.keys)):
                        if(nc_i.keys[idx] == key):
                            ncc_idx = self._get_page_by_id(nc_i.children[idx])
                            nc_i.keys[idx] = self._max_key(ncc_idx)
                            break

                self._set_page_by_id(node, id)                
                self._set_page_by_id(nc_i, cur_id)
                self._set_page_by_id(nc_iplus, right_id)
            # join con izquierdo
            elif i > 0:
                self._join(nc_iminus, node.keys[i - 1], nc_i)
                nc_iminus.next_page = nc_i.next_page
                deleted_node_id = node.children[i]
                nc_i.deleted = -1
                node.children[i] = -1
                self._pop_element(node, i - 1)

                self._set_page_by_id(node, id)
                self._set_page_by_id(nc_i, cur_id)
                self._set_page_by_id(nc_iminus, left_id)

                i = i - 1
            # join con derecho
            else:
                self._join(nc_i, node.keys[i], nc_iplus)
                nc_i.next_page = nc_iplus.next_page
                nc_iplus.deleted = -1
                node.children[i + 1] = -1
                self._pop_element(node, i)
                if not node.is_leaf and not nc_i.is_leaf:
                    for idx in range(len(nc_i.keys)):
                        if(nc_i.keys[idx] == key):
                            ncc_idx = self._get_page_by_id(nc_i.children[idx])
                            nc_i.keys[idx] = self._max_key(ncc_idx)
                            break  
                self._set_page_by_id(node, id)
                self._set_page_by_id(nc_i, cur_id)
                self._set_page_by_id(nc_iplus, right_id)
   
        if i < node.count and node.keys[i] == key:
            nc_i = self._get_page_by_id(node.children[i])
            key = self._max_key(nc_i)
            node.keys[i] = key
            self._set_page_by_id(node, id)            

    def _pop_element(self, 
                     node: Page, 
                     pos: int
                     ) -> None:
        i = pos
        while i < node.count - 1:
            node.keys[i] = node.keys[i + 1]
            node.children[i + 1] = node.children[i + 2]
            node.records[i] = node.records[i + 1]
            i += 1
        node.count -= 1

    def _extract_last(self, 
                      node: Page
                    ) -> ExtractionResult:
        result = ExtractionResult()
        result.key = node.keys[node.count - 1]
        result.right_tree = node.children[node.count]
        if (not node.is_leaf):
            node.count -= 1
        return result

    def _extract_first(self, 
                       node: Page
                       ) -> ExtractionResult:
        result = ExtractionResult()
        result.key = node.keys[0]
        result.left_tree = node.children[0]
        i = 0
        while i < node.count - 1:
            node.keys[i] = node.keys[i + 1]
            node.children[i] = node.children[i + 1]
            i += 1
        node.children[i] = node.children[i + 1]
        node.count -= 1
        return result
    
    def _relocate_left(self, 
                       node: Page, 
                       key: Any, 
                       left_tree: int=-1
                       ) -> None:
        i = node.count - 1
        while i >= 0 and key < node.keys[i]:
            node.keys[i + 1] = node.keys[i]
            node.children[i + 2] = node.children[i + 1]
            i -= 1
        node.children[i + 2] = node.children[i + 1]
        i += 1
        node.keys[i] = key
        node.children[i] = left_tree
        node.count += 1

    def _max_key(self, 
                 node: Page
                 ) -> Any:
        while not node.is_leaf:
            node = self._get_page_by_id(node.children[node.count])
        return node.keys[node.count-1] 
    
    def _join(self, 
              left_node: Page, 
              middle: Any, 
              right_node: Page
              ) -> None:

        if not left_node.is_leaf:
            self._relocate_right(left_node, middle, right_tree=right_node.children[0])

        for i in range(right_node.count):
            self._relocate_right(left_node, right_node.keys[i], right_tree=right_node.children[i + 1])

    def _find_leaf_for(self, key: Any) -> int:
        if self._page_count() == 0 or self.root_page == -1:
            return -1
        pid = self.root_page
        while pid != -1:
            node = self._get_page_by_id(pid)
            if node.is_leaf:
                return pid
            i = 0
            while i < node.count and key > node.keys[i]:
                i += 1
            pid = node.children[i]
        return -1

    def _lower_bound(self, arr, n, x):
        """
        Devuelve el índice más pequeño i en [0, n] tal que arr[i] >= x.
        Si todos los arr[0..n-1] < x, retorna n.
        - arr: lista de claves del nodo (puede tener basura después de n)
        - n:   node.count (número de claves válidas)
        - x:   clave a buscar (ya codificada si corresponde)
        """
        lo, hi = 0, n
        while lo < hi:
            mid = (lo + hi) // 2
            if arr[mid] < x:
                lo = mid + 1
            else:
                hi = mid
        return lo