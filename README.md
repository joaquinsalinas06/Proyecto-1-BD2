# Gramática en formato EBNF

```ebnf
statement = create_statement | select_statement | insert_statement | delete_statement ;

create_statement = create_table_statement | create_table_from_file_statement ;

create_table_statement = "CREATE" "TABLE" identifier "(" column_definition { "," column_definition } ")" ;

create_table_from_file_statement = "CREATE" "TABLE" identifier "FROM" "FILE" string "USING" "INDEX" index_type "(" column_identifier ")" ;

column_definition = identifier data_type [ "KEY" ] [ "INDEX" index_type ] ;

data_type = "INT"
          | "FLOAT"
          | "DATE"
          | "VARCHAR" "[" integer "]"
          | "ARRAY" "[" integer "]" "[" base_data_type "]" ;

base_data_type = "INT" | "FLOAT" | "DATE" ;

index_type = "SEQ" | "BTREE" | "HASH" | "ISAM" | "RTREE" ;

select_statement = "SELECT" column_list "FROM" identifier [ where_clause ] [ order_clause ] [ limit_clause ] ;

column_list = "*" | identifier { "," identifier } ;

where_clause = "WHERE" condition ;

order_clause = "ORDER" "BY" identifier [ "ASC" | "DESC" ] ;

limit_clause = "LIMIT" integer ;

insert_statement = "INSERT" "INTO" identifier "VALUES" "(" value { "," value } ")" ;

delete_statement = "DELETE" "FROM" identifier [ where_clause ] ;

condition = or_condition ;

or_condition = and_condition { "OR" and_condition } ;

and_condition = basic_condition { "AND" basic_condition } ;

basic_condition = "(" condition ")"
                | comparison_condition
                | between_condition
                | spatial_in_condition
                | spatial_knn_condition ;

comparison_condition = identifier comparison_operator value ;

comparison_operator = "=" | "!=" | "<" | "<=" | ">" | ">=" ;

between_condition = identifier "BETWEEN" value "AND" value ;

spatial_in_condition = identifier "IN" "(" point "," number ")" ;

spatial_knn_condition = identifier "KNN" "(" point "," integer ")" ;

value = number | string | array | point ;

array = "(" number_or_string { "," number_or_string } ")"
      | "[" number_or_string { "," number_or_string } "]" ;

point = "(" number "," number ")" ;

number_or_string = number | string ;

number = integer | float ;

identifier = letter { letter | digit | "_" } ;

column_identifier = identifier | string ;

integer = digit { digit } ;

float = digit { digit } "." digit { digit } ;

string = '"' { character } '"' | "'" { character } "'" ;

letter = "A" | "B" | ... | "Z" | "a" | "b" | ... | "z" ;

digit = "0" | "1" | "2" | "3" | "4" | "5" | "6" | "7" | "8" | "9" ;

character = any_printable_character_except_quote ;
```

## Tipos de datos soportados

- **INT**: Números enteros
- **FLOAT**: Números de punto flotante
- **VARCHAR[tamaño]**: Cadenas de longitud variable con tamaño máximo especificado
- **DATE**: Fechas en formato YYYY-MM-DD
- **ARRAY[dimensión][tipo_base]**: Arrays con dimensión y tipo base especificados

## Tipos de índices

- **SEQ**: Índice secuencial
- **BTREE**: Índice B-Tree
- **HASH**: Índice Hash
- **ISAM**: Índice ISAM
- **RTREE**: Índice R-Tree (para datos espaciales)

## Operadores

### Operadores de comparación
- `=` (igual)
- `!=` (no igual)
- `<` (menor que)
- `<=` (menor o igual que)
- `>` (mayor que)
- `>=` (mayor o igual que)

### Operadores lógicos
- `AND` (y lógico)
- `OR` (o lógico)

### Operadores especiales
- `BETWEEN` (condición de rango)
- `IN` (condición espacial punto-en-círculo)
- `KNN` (k-vecinos más cercanos)

## Formatos de valores

### Arrays
- Formato con paréntesis: `(1, 2, 3)`
- Formato con corchetes: `[1, 2, 3]`

### Puntos espaciales
- Formato: `(x, y)` donde x e y son números
- Ejemplo: `(10.5, 20.3)`

### Cadenas
- Comillas simples: `'Hola Mundo'`
- Comillas dobles: `"Hola Mundo"`

### Formato de fechas
- Formato: `YYYY-MM-DD`
- Ejemplo: `"2023-12-25"`