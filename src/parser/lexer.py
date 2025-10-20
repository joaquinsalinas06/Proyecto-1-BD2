from typing import List
from .tokens import Token, TokenType, KEYWORDS

class LexerError(Exception):
    pass

class Lexer:
    def __init__(self, source: str):
        self.source = source
        self.tokens = []
        self.start = 0      # Inicio del token actual
        self.current = 0    # Carácter actual
        self.line = 1       # Línea actual
        self.column = 1     # Columna actual
    
    def scan_tokens(self) -> List[Token]:
        while not self._is_at_end():
            self.start = self.current
            self._scan_token()
        
        # Agregar token EOF al final
        self.tokens.append(Token(TokenType.EOF, "", self.line, self.column))
        return self.tokens
    
    def _scan_token(self):
        char = self._advance()
        
        # Ignorar espacios en blanco
        if char.isspace():
            if char == '\n':
                self.line += 1
                self.column = 1
            return
        
        # Operadores de comparación
        if char == '=':
            self._add_token(TokenType.EQUALS)
        elif char == '!':
            if self._match('='):
                self._add_token(TokenType.NOT_EQUALS)
            else:
                raise LexerError(f"Carácter inesperado '!' en línea {self.line}")
        elif char == '<':
            if self._match('='):
                self._add_token(TokenType.LESS_EQUALS)
            else:
                self._add_token(TokenType.LESS_THAN)
        elif char == '>':
            if self._match('='):
                self._add_token(TokenType.GREATER_EQUALS)
            else:
                self._add_token(TokenType.GREATER_THAN)

        elif char == '(':
            self._add_token(TokenType.LPAREN)
        elif char == ')':
            self._add_token(TokenType.RPAREN)
        elif char == '[':
            self._add_token(TokenType.LBRACKET)
        elif char == ']':
            self._add_token(TokenType.RBRACKET)
        elif char == ',':
            self._add_token(TokenType.COMMA)
        elif char == ';':
            self._add_token(TokenType.SEMICOLON)
        elif char == '*':
            self._add_token(TokenType.ASTERISK)

        elif char == '"' or char == "'":
            self._string(char)

        elif char == '-':
            if self._peek().isdigit():
                self._number()
            else:
                self._add_token(TokenType.MINUS)
                        
        elif char.isdigit():
            self._number()
        
        # Id's y palabras clave
        elif char.isalpha() or char == '_':
            self._id()
        
        else:
            raise LexerError(f"Carácter inesperado '{char}' en línea {self.line}")
    
    def _string(self, quote_char: str):
        start_line = self.line
        
        while not self._is_at_end():
            if self._peek() == quote_char:
                if self._peek_next() == quote_char:
                    self._advance() 
                    self._advance()
                else:

                    break
            elif self._peek() == '\n':
                self.line += 1
                self.column = 1
                self._advance()
            else:
                self._advance()
        
        if self._is_at_end():
            raise LexerError(f"String sin cerrar iniciado en línea {start_line}")

        self._advance()  # consume closing quote
        
        # Obtener el valor del string (sin las comillas)
        value = self.source[self.start + 1:self.current - 1]
        # Unescape doubled quotes: '' -> '
        value = value.replace(quote_char + quote_char, quote_char)
        self._add_token(TokenType.STRING, value)
    
    def _number(self):
        while self._peek().isdigit():
            self._advance()
        
        # Verificar si es decimal
        if self._peek() == '.' and self._peek_next().isdigit():
            # Consumir el punto
            self._advance()
            
            # Consumir dígitos decimales
            while self._peek().isdigit():
                self._advance()
            
            value = float(self.source[self.start:self.current])
            self._add_token(TokenType.FLOAT, value)
        else:
            value = int(self.source[self.start:self.current])
            self._add_token(TokenType.INTEGER, value)
    
    def _id(self):
        while self._peek().isalnum() or self._peek() == '_':
            self._advance()
        
        text = self.source[self.start:self.current].upper()
        
        # Verificar si es una palabra clave o un id
        token_type = KEYWORDS.get(text, TokenType.ID)
        
        #Si no encontro nada en nuestras palabras clave, es un ID
        if token_type == TokenType.ID:
            text = self.source[self.start:self.current]
        
        self._add_token(token_type, text)
    
    def _match(self, expected: str) -> bool:
        if self._is_at_end():
            return False
        if self.source[self.current] != expected:
            return False
        
        self.current += 1
        self.column += 1
        return True
    
    def _peek(self) -> str:
        if self._is_at_end():
            return '\0'
        return self.source[self.current]
    
    def _peek_next(self) -> str:
        if self.current + 1 >= len(self.source):
            return '\0'
        return self.source[self.current + 1]
    
    def _advance(self) -> str:
        char = self.source[self.current]
        self.current += 1
        self.column += 1
        return char
    
    def _is_at_end(self) -> bool:
        return self.current >= len(self.source)
    
    def _add_token(self, token_type: TokenType, literal=None):
        text = self.source[self.start:self.current]
        token = Token(token_type, literal if literal is not None else text, 
                     self.line, self.column - len(text))
        self.tokens.append(token)
