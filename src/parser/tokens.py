from enum import Enum

# Definimos un enum con todos los tokens que nuestro lenguaje SQL soporta
class TokenType(Enum):
    ID = "ID"
    INTEGER = "INTEGER"
    FLOAT = "FLOAT"
    STRING = "STRING"
    DATE = "DATE"
    CREATE = "CREATE"
    TABLE = "TABLE"
    FROM = "FROM"
    FILE = "FILE"
    USING = "USING"
    INDEX = "INDEX"
    SELECT = "SELECT"
    INSERT = "INSERT"
    INTO = "INTO"
    VALUES = "VALUES"
    DELETE = "DELETE"
    WHERE = "WHERE"
    ORDER = "ORDER"
    BY = "BY"
    LIMIT = "LIMIT"
    AND = "AND"
    OR = "OR"
    BETWEEN = "BETWEEN"
    IN = "IN"
    KNN = "KNN"
    ASC = "ASC"
    DESC = "DESC"
    KEY = "KEY"
    PRIMARY = "PRIMARY"
    INT = "INT"
    FLOAT_TYPE = "FLOAT"
    VARCHAR = "VARCHAR"
    DATE_TYPE = "DATE"
    ARRAY = "ARRAY"
    SEQ = "SEQ"
    BTREE = "BTREE"
    HASH = "HASH"
    ISAM = "ISAM"
    RTREE = "RTREE"
    EQUALS = "="
    NOT_EQUALS = "!="
    LESS_THAN = "<"
    LESS_EQUALS = "<="
    GREATER_THAN = ">"
    GREATER_EQUALS = ">="
    LPAREN = "("
    RPAREN = ")"
    LBRACKET = "["
    RBRACKET = "]"
    COMMA = ","
    SEMICOLON = ";"
    ASTERISK = "*"
    EOF = "EOF"


class Token:
    def __init__(self, token_type: TokenType, lexeme: str, line: int = 1, column: int = 1):
        self.type = token_type
        self.lexeme = lexeme
        self.line = line
        self.column = column
    
    def __str__(self):
        return f"Token({self.type}, '{self.lexeme}', {self.line}:{self.column})"
    
    def __repr__(self):
        return self.__str__()


KEYWORDS = {
    'CREATE': TokenType.CREATE,
    'TABLE': TokenType.TABLE,
    'FROM': TokenType.FROM,
    'FILE': TokenType.FILE,
    'USING': TokenType.USING,
    'INDEX': TokenType.INDEX,
    'SELECT': TokenType.SELECT,
    'INSERT': TokenType.INSERT,
    'INTO': TokenType.INTO,
    'VALUES': TokenType.VALUES,
    'DELETE': TokenType.DELETE,
    'WHERE': TokenType.WHERE,
    'ORDER': TokenType.ORDER,
    'BY': TokenType.BY,
    'LIMIT': TokenType.LIMIT,
    'AND': TokenType.AND,
    'OR': TokenType.OR,
    'BETWEEN': TokenType.BETWEEN,
    'IN': TokenType.IN,
    'KNN': TokenType.KNN,
    'ASC': TokenType.ASC,
    'DESC': TokenType.DESC,
    'KEY': TokenType.KEY,
    'PRIMARY': TokenType.PRIMARY,
    'INT': TokenType.INT,
    'FLOAT': TokenType.FLOAT_TYPE,
    'VARCHAR': TokenType.VARCHAR,
    'DATE': TokenType.DATE_TYPE,
    'ARRAY': TokenType.ARRAY,
    'SEQ': TokenType.SEQ,
    'BTREE': TokenType.BTREE,
    'HASH': TokenType.HASH,
    'ISAM': TokenType.ISAM,
    'RTREE': TokenType.RTREE,
}
