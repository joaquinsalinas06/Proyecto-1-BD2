from typing import List, Optional
from .tokens import Token, TokenType
from .lexer import Lexer
from .ast import *

class ParseError(Exception):
    pass

class SQLParser:
    def __init__(self):
        self.tokens = []
        self.current = 0
    
    def parse(self, source: str) -> List[Statement]:
        lexer = Lexer(source)
        self.tokens = lexer.scan_tokens()
        self.current = 0

        return self._parse_statements()

    def _parse_statements(self) -> List[Statement]:
        statements = []

        # Leemos todos los statements hasta EOF, en caso nos encontraomos con un ;, verificamos si el usuario no lo ingreso para terminar el statement, si no hay nada despues
        # Hay que ver si es que realmente terminamos, si no paso nada de eso, entonces error
        # program -> statement (';' statement)* ';'+
        while not self._peek().type == TokenType.EOF:
            stmt = self._parse_statement()
            statements.append(stmt)

            if self._match(TokenType.SEMICOLON):
                if self._peek().type == TokenType.EOF:
                    break
                continue
            else:
                if self._peek().type == TokenType.EOF:
                    break
                else:
                    raise ParseError(f"Se esperaba ';' después de la sentencia en línea {self._peek().line}")

        return statements


    def _parse_statement(self) -> Statement: # statement -> create_statement | select_statement | insert_statement | delete_statement
        if self._check(TokenType.CREATE):
            return self._parse_create_statement()
        elif self._check(TokenType.SELECT):
            return self._parse_select_statement()
        elif self._check(TokenType.INSERT):
            return self._parse_insert_statement()
        elif self._check(TokenType.DELETE):
            return self._parse_delete_statement()
        else:
            raise ParseError(f"Sentencia inesperada: {self._peek().lexeme}")
    
    def _parse_create_statement(self) -> Union[CreateTableStmt, CreateTableFileStmt]: # create_statement -> CREATE TABLE name (column_definitions) | CREATE TABLE name FROM FILE "path" USING INDEX type(column)
        self._consume(TokenType.CREATE, "Se esperaba 'CREATE'")
        self._consume(TokenType.TABLE, "Se esperaba 'TABLE'")
        
        table_name = self._consume(TokenType.ID, "Se esperaba nombre de tabla").lexeme
        
        if self._check(TokenType.FROM):
            return self._parse_create_from_file(table_name)
        else:
            return self._parse_create_with_columns(table_name)
    
    def _parse_create_with_columns(self, table_name: str) -> CreateTableStmt: # CREATE TABLE name (column_definitions)
        self._consume(TokenType.LPAREN, "Se esperaba '('")
        
        columns = []
        columns.append(self._parse_column_definition())
        
        while self._match(TokenType.COMMA):
            columns.append(self._parse_column_definition())
        
        self._consume(TokenType.RPAREN, "Se esperaba ')'")
        
        return CreateTableStmt(table_name, columns)
    
    def _parse_create_from_file(self, table_name: str) -> CreateTableFileStmt:
        # CREATE TABLE name FROM FILE "path" USING PRIMARY INDEX type(column), INDEX type(column), ...
        self._consume(TokenType.FROM, "Se esperaba 'FROM'")
        self._consume(TokenType.FILE, "Se esperaba 'FILE'")

        file_path = self._consume(TokenType.STRING, "Se esperaba ruta del archivo").lexeme
        
        self._consume(TokenType.USING, "Se esperaba 'USING'")

        # Parsear lista de índices
        indexes = []

        # Primer indice (debe ser PRIMARY)
        if self._match(TokenType.PRIMARY):
            self._consume(TokenType.INDEX, "Se esperaba 'INDEX' después de 'PRIMARY'")
            index_spec = self._parse_index_specification(is_primary=True)
            indexes.append(index_spec)
        else:
            raise ParseError("Se esperaba 'PRIMARY INDEX' como primer índice")

        # Índices adicionales opcionales (secundarios)
        while self._match(TokenType.COMMA):
            self._consume(TokenType.INDEX, "Se esperaba 'INDEX'")
            index_spec = self._parse_index_specification(is_primary=False)
            indexes.append(index_spec)

        return CreateTableFileStmt(table_name, file_path, indexes)

    def _parse_index_specification(self, is_primary: bool) -> 'IndexSpec':
        index_type = self._parse_index_type()
        if is_primary:
            if index_type not in [IndexType.SEQ, IndexType.ISAM, IndexType.BTREE]:
                raise ParseError(f"El tipo de índice {index_type.value} no puede usarse como índice de clave primaria. "
                                 f"Solo SEQ, ISAM y BTREE están permitidos para columnas de clave primaria.")
        else:
            if index_type not in [IndexType.HASH, IndexType.RTREE, IndexType.BTREE]:
                raise ParseError(f"El tipo de índice {index_type.value} no puede usarse como índice secundario. "
                                 f"Solo HASH, RTREE y BTREE están permitidos para índices secundarios.")

        self._consume(TokenType.LPAREN, "Se esperaba '('")

        if self._check(TokenType.ID):
            column_name = self._consume(TokenType.ID, "Se esperaba nombre de columna").lexeme
        elif self._check(TokenType.STRING):
            column_name = self._consume(TokenType.STRING, "Se esperaba nombre de columna").lexeme
        else:
            raise ParseError("Se esperaba nombre de columna (ID o STRING)")

        self._consume(TokenType.RPAREN, "Se esperaba ')'")

        return IndexSpec(index_type, column_name, is_primary)
    
    def _parse_column_definition(self) -> ColumnDef: # column_definition -> name data_type [KEY] [INDEX index_type]
        name = self._consume(TokenType.ID, "Se esperaba nombre de columna").lexeme
        data_type, size, element_type = self._parse_data_type()
        
        is_key = False
        if self._match(TokenType.KEY):
            is_key = True
        
        index_type = None
        if self._match(TokenType.INDEX):
            index_type = self._parse_index_type()
            if is_key:
                if index_type not in [IndexType.SEQ, IndexType.ISAM, IndexType.BTREE]:
                    raise ParseError(f"Index type {index_type.value} cannot be used as primary key index. "
                                f"Only SEQ, ISAM, and BTREE are allowed for primary key columns.")
            else:
                if index_type not in [IndexType.HASH, IndexType.RTREE, IndexType.BTREE]:
                    raise ParseError(f"Index type {index_type.value} cannot be used as secondary index. "
                                f"Only HASH, RTREE, and BTREE are allowed for secondary indexes.")

        if data_type == DataType.ARRAY:
            array_dimensions = size
            size = None
        else:
            array_dimensions = None

        return ColumnDef(name, data_type, size, element_type, is_key, index_type, array_dimensions)
    
    def _parse_data_type(self) -> tuple[DataType, Optional[int], Optional[DataType]]: # data_type -> INT | FLOAT | DATE | VARCHAR[size] | ARRAY[dimension][base_data_type]
        
        if self._match(TokenType.INT):
            return DataType.INT, None, None
        elif self._match(TokenType.FLOAT_TYPE):
            return DataType.FLOAT, None, None
        elif self._match(TokenType.DATE_TYPE):
            return DataType.DATE, None, None
        elif self._match(TokenType.VARCHAR):
            self._consume(TokenType.LBRACKET, "Se esperaba '['")
            size = self._consume(TokenType.INTEGER, "Se esperaba tamaño").lexeme
            self._consume(TokenType.RBRACKET, "Se esperaba ']'")
            return DataType.VARCHAR, int(size), None
        elif self._match(TokenType.ARRAY):
            self._consume(TokenType.LBRACKET, "Se esperaba '['")
            dimension = int(self._consume(TokenType.INTEGER, "Se esperaba dimensión del array").lexeme)
            self._consume(TokenType.RBRACKET, "Se esperaba ']'")
            self._consume(TokenType.LBRACKET, "Se esperaba segundo '['")
            element_type = None

            if self._match(TokenType.INT):
                element_type = DataType.INT
            elif self._match(TokenType.FLOAT_TYPE):
                element_type = DataType.FLOAT
            elif self._match(TokenType.DATE_TYPE):
                element_type = DataType.DATE
            else:
                raise ParseError(f"Tipo base inesperado: {self._peek().lexeme}")
            
            self._consume(TokenType.RBRACKET, "Se esperaba ']'")
            return DataType.ARRAY, dimension, element_type
        else:
            raise ParseError(f"Tipo de dato inesperado: {self._peek().lexeme}")
   
    def _parse_index_type(self) -> IndexType: # index_type -> SEQ | BTREE | HASH | ISAM | RTREE
        if self._match(TokenType.SEQ):
            return IndexType.SEQ
        elif self._match(TokenType.BTREE):
            return IndexType.BTREE
        elif self._match(TokenType.HASH):
            return IndexType.HASH
        elif self._match(TokenType.ISAM):
            return IndexType.ISAM
        elif self._match(TokenType.RTREE):
            return IndexType.RTREE
        else:
            raise ParseError(f"Tipo de índice inesperado: {self._peek().lexeme}")
    
    def _parse_select_statement(self) -> SelectStmt: # select_statement -> SELECT column_list FROM table_name [WHERE condition] [ORDER BY column [ASC|DESC]] [LIMIT number]
        self._consume(TokenType.SELECT, "Se esperaba 'SELECT'")

        columns = []
        if self._match(TokenType.ASTERISK):
            columns = ["*"]
        else:
            columns.append(self._consume(TokenType.ID, "Se esperaba nombre de columna").lexeme)
            while self._match(TokenType.COMMA):
                columns.append(self._consume(TokenType.ID, "Se esperaba nombre de columna").lexeme)
        
        self._consume(TokenType.FROM, "Se esperaba 'FROM'")
        table_name = self._consume(TokenType.ID, "Se esperaba nombre de tabla").lexeme
        
        # WHERE opcional
        where_condition = None
        if self._match(TokenType.WHERE):
            where_condition = self._parse_condition()
        
        # ORDER BY opcional
        order_by = None
        order_desc = False
        if self._match(TokenType.ORDER):
            self._consume(TokenType.BY, "Se esperaba 'BY'")
            order_by = self._consume(TokenType.ID, "Se esperaba nombre de columna").lexeme
            
            if self._match(TokenType.DESC):
                order_desc = True
            elif self._match(TokenType.ASC):
                order_desc = False
        
        # LIMIT opcional
        limit = None
        if self._match(TokenType.LIMIT):
            limit = int(self._consume(TokenType.INTEGER, "Se esperaba número").lexeme)
        
        return SelectStmt(table_name, columns, where_condition, order_by, order_desc, limit)
    
    def _parse_insert_statement(self) -> InsertStmt: # insert_statement -> INSERT INTO table VALUES (value, value, ...)
        
        self._consume(TokenType.INSERT, "Se esperaba 'INSERT'")
        self._consume(TokenType.INTO, "Se esperaba 'INTO'")
        
        table_name = self._consume(TokenType.ID, "Se esperaba nombre de tabla").lexeme
        
        self._consume(TokenType.VALUES, "Se esperaba 'VALUES'")
        self._consume(TokenType.LPAREN, "Se esperaba '('")
        
        values = []
        values.append(self._parse_value())
        
        while self._match(TokenType.COMMA):
            values.append(self._parse_value())
        
        self._consume(TokenType.RPAREN, "Se esperaba ')'")
        
        return InsertStmt(table_name, values)
    
    def _parse_delete_statement(self) -> DeleteStmt: # delete_statement -> DELETE FROM table [WHERE condition]
        self._consume(TokenType.DELETE, "Se esperaba 'DELETE'")
        self._consume(TokenType.FROM, "Se esperaba 'FROM'")
        
        table_name = self._consume(TokenType.ID, "Se esperaba nombre de tabla").lexeme
        
        where_condition = None
        if self._match(TokenType.WHERE):
            where_condition = self._parse_condition()
        
        return DeleteStmt(table_name, where_condition)
    
    def _parse_condition(self) -> Condition: # condition -> or_condition
        return self._parse_or_condition()
    
    def _parse_or_condition(self) -> Condition: # or_condition -> and_condition { OR and_condition }
        condition = self._parse_and_condition()
        
        while self._match(TokenType.OR):
            operator = LogicOp.OR
            right = self._parse_and_condition()
            condition = LogicCond(condition, operator, right)
        
        return condition
    
    def _parse_and_condition(self) -> Condition: # and_condition -> basic_condition { AND basic_condition }
        condition = self._parse_basic_condition()
        
        while self._match(TokenType.AND):
            operator = LogicOp.AND
            right = self._parse_basic_condition()
            condition = LogicCond(condition, operator, right)
        
        return condition
    
    def _parse_basic_condition(self) -> Condition:  # basic_condition -> ( condition ) | comparison_condition | between_condition | spatial_in_condition | spatial_knn_condition
        if self._match(TokenType.LPAREN):
            condition = self._parse_condition()
            self._consume(TokenType.RPAREN, "Se esperaba ')'")
            return condition

        column = self._consume(TokenType.ID, "Se esperaba nombre de columna").lexeme
        
        if self._match(TokenType.BETWEEN):
            return self._parse_between_condition(column)
        elif self._check(TokenType.IN):
            return self._parse_spatial_in_condition(column)
        elif self._check(TokenType.KNN):
            return self._parse_spatial_knn_condition(column)
        else:
            return self._parse_comparison_condition(column)
    
    def _parse_comparison_condition(self, column: str) -> CompCond:
        if self._match(TokenType.EQUALS):
            operator = CompOp.EQUALS
        elif self._match(TokenType.NOT_EQUALS):
            operator = CompOp.NOT_EQUALS
        elif self._match(TokenType.LESS_EQUALS):
            operator = CompOp.LESS_EQUALS
        elif self._match(TokenType.LESS_THAN):
            operator = CompOp.LESS_THAN
        elif self._match(TokenType.GREATER_EQUALS):
            operator = CompOp.GREATER_EQUALS
        elif self._match(TokenType.GREATER_THAN):
            operator = CompOp.GREATER_THAN
        else:
            raise ParseError(f"Operador de comparación inesperado: {self._peek().lexeme}")
        value = self._parse_value()
        return CompCond(column, operator, value)
    
    def _parse_between_condition(self, column: str) -> BetweenCond:
        start_value = self._parse_value()
        self._consume(TokenType.AND, "Se esperaba 'AND'")
        end_value = self._parse_value()
        return BetweenCond(column, start_value, end_value)
    
    def _parse_spatial_in_condition(self, column: str) -> SpatialInCond:
        self._consume(TokenType.IN, "Se esperaba 'IN'")
        self._consume(TokenType.LPAREN, "Se esperaba '('")
        
        point = self._parse_point()
        self._consume(TokenType.COMMA, "Se esperaba ','")
        
        radius_token = self._consume_number("Se esperaba radio")
        radius = float(radius_token.lexeme)
        
        self._consume(TokenType.RPAREN, "Se esperaba ')'")
        
        return SpatialInCond(column, point, radius)
    
    def _parse_spatial_knn_condition(self, column: str) -> SpatialKNNCond:
        self._consume(TokenType.KNN, "Se esperaba 'KNN'")
        self._consume(TokenType.LPAREN, "Se esperaba '('")
        
        point = self._parse_point()
        self._consume(TokenType.COMMA, "Se esperaba ','")
        
        k = int(self._consume(TokenType.INTEGER, "Se esperaba número entero").lexeme)
        
        self._consume(TokenType.RPAREN, "Se esperaba ')'")
        
        return SpatialKNNCond(column, point, k)
    
    def _parse_value(self) -> Value: # value -> number | string | array | point
        if self._check(TokenType.INTEGER) or self._check(TokenType.FLOAT):
            token = self._consume_number("Se esperaba número")
            literal = token.lexeme
            if isinstance(literal, int):
                return Value(literal, DataType.INT)
            elif isinstance(literal, float):
                return Value(literal, DataType.FLOAT)
            elif isinstance(literal, str):
                # Detectar si es una fecha (formato YYYY-MM-DD)
                if len(literal) == 10 and literal[4] == '-' and literal[7] == '-':
                    year, month, day = literal.split('-')
                    int(year), int(month), int(day)  # Validar que son números
                    return Value(literal, DataType.DATE)
                return Value(literal, DataType.VARCHAR)
            else:
                raise ValueError(f"Tipo de literal no soportado: {type(literal)}")
        
        elif self._check(TokenType.STRING):
            token = self._consume(TokenType.STRING, "Se esperaba string")
            literal = token.lexeme
            if isinstance(literal, int):
                return Value(literal, DataType.INT)
            elif isinstance(literal, float):
                return Value(literal, DataType.FLOAT)
            elif isinstance(literal, str):
                # Detectar si es una fecha (formato YYYY-MM-DD)
                if len(literal) == 10 and literal[4] == '-' and literal[7] == '-':
                    year, month, day = literal.split('-')
                    int(year), int(month), int(day)  # Validar que son números
                    return Value(literal, DataType.DATE)
                return Value(literal, DataType.VARCHAR)
            else:
                raise ValueError(f"Tipo de literal no soportado: {type(literal)}")
        
        elif self._check(TokenType.LPAREN):
            self._consume(TokenType.LPAREN, "Se esperaba '('")

            values = []
            values.append(self._parse_number_or_string())

            while self._match(TokenType.COMMA):
                values.append(self._parse_number_or_string())

            self._consume(TokenType.RPAREN, "Se esperaba ')'")

            # All tuples are treated as arrays (including spatial points)
            # Convert to tuple for consistency
            return Value(tuple(values), DataType.ARRAY)
        
        elif self._check(TokenType.LBRACKET):
            self._consume(TokenType.LBRACKET, "Se esperaba '['")
            values = []
            values.append(self._parse_number_or_string())
            while self._match(TokenType.COMMA):
                values.append(self._parse_number_or_string())
            self._consume(TokenType.RBRACKET, "Se esperaba ']'")
            return Value(values, DataType.ARRAY)
        
        else:
            raise ParseError(f"Valor inesperado: {self._peek().lexeme}")
    
    def _parse_point(self) -> tuple:
        self._consume(TokenType.LPAREN, "Se esperaba '('")

        coordinates = []

        # Parse first coordinate
        coord_token = self._consume_number("Se esperaba coordenada")
        coordinates.append(float(coord_token.lexeme))

        # Parse remaining coordinates
        while self._match(TokenType.COMMA):
            # Check if next token is a number (coordinate) or closing paren
            if self._check(TokenType.RPAREN):
                # This comma was for the next parameter (radius or k), not another coordinate
                self.current -= 1  # Put the comma back
                break

            coord_token = self._consume_number("Se esperaba coordenada")
            coordinates.append(float(coord_token.lexeme))

        self._consume(TokenType.RPAREN, "Se esperaba ')'")

        return tuple(coordinates)
    
    def _parse_number_or_string(self):
        if self._check(TokenType.INTEGER) or self._check(TokenType.FLOAT):
            token = self._consume_number("Se esperaba número")
            return token.lexeme
        elif self._check(TokenType.STRING):
            token = self._consume(TokenType.STRING, "Se esperaba string")
            return token.lexeme
        else:
            raise ParseError(f"Se esperaba número o string: {self._peek().lexeme}")
        

    def _match(self, *types: TokenType) -> bool:
        for token_type in types:
            if self._check(token_type):
                self._advance()
                return True
        return False
    
    def _check(self, token_type: TokenType) -> bool:
        if self._peek().type == TokenType.EOF:
            return False
        return self._peek().type == token_type
    
    def _advance(self) -> Token:
        if not self._peek().type == TokenType.EOF:
            self.current += 1
        return self.tokens[self.current - 1]
    
    def _peek(self) -> Token:
        return self.tokens[self.current]
    
    def _consume(self, token_type: TokenType, message: str) -> Token:
        if self._check(token_type):
            return self._advance()
        
        current_token = self._peek()
        raise ParseError(f"{message}. Se encontró '{current_token.lexeme}' en línea {current_token.line}")
    
    def _consume_number(self, message: str) -> Token:
        if self._check(TokenType.INTEGER) or self._check(TokenType.FLOAT):
            return self._advance()
        
        current_token = self._peek()
        raise ParseError(f"{message}. Se encontró '{current_token.lexeme}' en línea {current_token.line}")
