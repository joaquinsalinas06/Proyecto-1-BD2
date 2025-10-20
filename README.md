# Proyecto 1 - Organización e Indexación Eficiente de Archivos con Datos Multidimensionales

---

## 📑 Índice

1. [Introducción](#1-introducción)
2. [Técnicas de Indexación](#2-técnicas-de-indexación)
3. [Parser SQL](#3-parser-sql)
4. [Resultados Experimentales](#4-resultados-experimentales)
5. [Pruebas de Uso](#5-pruebas-de-uso)

---

## 1. Introducción

### Objetivo del Proyecto

### Descripción de la Aplicación

#### Combinación de Técnicas de Indexación

---

## 2. Técnicas de Indexación

### 2.1 Sequential File
Es una de las primeras estructuras vistas en el curso. Esta técnica mantiene los registros ordenados por una clave específica en un archivo principal, utilizando un archivo auxiliar para las inserciones nuevas. Se ha optimizado las búsquedas manteniendo unn orden claro y usando búsqueda binaria.

#### Algoritmo de Inserción
**Proceso:**
1. Se valida que el registro contenga la columna de indexación
2. El registro se inserta en el **archivo auxiliar** (`aux_file`)
3. Se actualizan los límites mínimo y máximo si es necesario
4. Se verifica si el archivo auxiliar alcanzó el umbral máximo (`max_auxiliary_records`, por defecto 5)
5. Si se alcanza el umbral, se ejecuta el proceso de **reconstrucción**:
   - Se leen todos los registros del archivo principal y auxiliar
   - Se combinan y ordenan por la clave de indexación
   - Se reescribe el archivo principal con todos los registros ordenados
   - Se vacía el archivo auxiliar

Con este procedimiento tenemos inserciones rápidas en O(1) al escribir en el archivo auxiliar. 

#### Algoritmo de Búsqueda
La búsqueda de un registro por clave utiliza búsqueda binaria en el archivo principal y búsqueda lineal en el auxiliar:

**Proceso:**
1. **Búsqueda en archivo principal:**
   - Se aplica búsqueda binaria sobre los registros ordenados
   - Complejidad: O(log n) donde n es el número de registros en el archivo principal
   - Al encontrar una coincidencia, se expande la búsqueda hacia ambos lados para encontrar duplicados
   
2. **Búsqueda en archivo auxiliar:**
   - Se realiza búsqueda lineal en el archivo auxiliar
   - Se agregan todos los registros con clave coincidente

Para el manejo de duplicados, el algoritmo propuesto busca hacia adelante y atrás desde la posición encontrada para obtener todos los registros con la misma clave y de esta forma asegurar que se retornen todos los resultados.


#### Algoritmo de Búsqueda por Rango
Aprovechando que el archivo principal está ordenado, se puede realizar una búsqueda eficiente por rango.

**Proceso:**
1. **Optimización temprana:** Se verifican los límites (`_min_bound`, `_max_bound`) para descartar rangos fuera del conjunto de datos
2. **Búsqueda binaria para límite inferior:**
   - Se encuentra la primera posición que cumple con `begin_key`
   - Se respeta el parámetro `begin_inclusive`
3. **Búsqueda binaria para límite superior:**
   - Se encuentra la última posición que cumple con `end_key`
   - Se respeta el parámetro `end_inclusive`
4. **Extracción de registros:** Se recorren secuencialmente las posiciones entre `start_pos` y `end_pos`
5. **Filtrado en archivo auxiliar:** Se realiza búsqueda lineal aplicando las condiciones del rango

#### Algoritmo de Eliminación
La eliminación física remueve registros tanto del archivo principal como del auxiliar:

**Proceso:**
1. Se leen todos los registros del archivo principal
2. Se filtran los registros cuya clave no coincide con la clave a eliminar
3. Si se eliminaron registros, se reescribe el archivo principal con los registros filtrados
4. Se actualiza el contador `_main_record_count`
5. Se repite el proceso para el archivo auxiliar
6. Se retorna `True` si se eliminó al menos un registro

Esta implementación realiza eliminación física (reescritura), no eliminación lógica (marcado). Esto garantiza recuperación de espacio pero tiene mayor costo computacional.

#### Análisis de Complejidad
| Operación | Mejor Caso | Caso Promedio | Peor Caso | Observaciones |
|-----------|------------|---------------|-----------|---------------|
| **Inserción** | O(1) | O(1) | O(n log n) | O(1) cuando no hay reconstrucción. O(n log n) durante reconstrucción (sorting). |
| **Búsqueda** | O(log n) | O(log n + k) | O(n + m) | k = duplicados, m = tamaño auxiliar. Peor caso cuando todos los registros están en auxiliar. |
| **Búsqueda por Rango** | O(log n + r) | O(log n + r) | O(n + m) | r = registros en rango. Búsqueda binaria para encontrar límites. |
| **Eliminación** | O(n) | O(n) | O(n + m) | Requiere leer y reescribir archivos completos. |

### 2.2 ISAM (Indexed Sequential Access Method)

#### Algoritmo de Inserción

#### Algoritmo de Búsqueda

#### Algoritmo de Búsqueda

#### Algoritmo de Búsqueda por Rango

#### Algoritmo de Eliminación

#### Análisis de Complejidad

### 2.3 Extendible Hashing

#### Algoritmo de Inserción

#### Algoritmo de Búsqueda

#### Limitación: No Soporta Búsqueda por Rango

#### Algoritmo de Eliminación

#### Análisis de Complejidad

### 2.4 B+ Tree

#### B+ Tree Clustered (Índice Primario)

##### Algoritmo de Inserción

##### Algoritmo de Búsqueda

##### Algoritmo de Búsqueda por Rango

##### Algoritmo de Eliminación

##### Análisis de Complejidad

#### B+ Tree Unclustered (Índice Secundario)

##### Algoritmo de Inserción

##### Algoritmo de Búsqueda

##### Algoritmo de Búsqueda por Rango

##### Algoritmo de Eliminación

##### Análisis de Complejidad

### 2.5 R-Tree (Datos Espaciales)
Estructura que guarda datos multidimensionales utilizando rectángulos mínimos (MBR) que engloban los objetos. Ideal para consultas espaciales como búsqueda por rango y K-NN.

Algunas consideraciones a tener en cuenta son:
- `leaf_capacity`: Número máximo de entradas por nodo hoja (por defecto 50)
- `fill_factor`: Factor de llenado de nodos (0.7 = 70%)
- `dimension`: Dimensionalidad del espacio (por defecto 2)
#### Algoritmo de Inserción
La inserción en R-Tree se realiza mediante la biblioteca `rtree`:

**Proceso:**
1. Se valida que el registro contenga la columna espacial y la clave primaria
2. Se verifica que el punto tenga el número correcto de dimensiones
3. Se extrae el punto del registro y se convierte a tupla
4. Se crea un MBR (Minimum Bounding Rectangle) colapsado: `(x, y, x, y)` para un punto 2D
5. Se inserta en el índice usando `rtree_index.insert(pk, mbr, obj=point)`
6. Se incrementa el contador de registros

#### Algoritmo de Búsqueda Espacial
La búsqueda exacta de un punto utiliza búsqueda por intersección con tolerancia epsilon:

**Proceso:**
1. Se valida que la clave sea un punto con las dimensiones correctas
2. Se crea un MBR pequeño alrededor del punto usando epsilon (1e-9)
3. Se buscan intersecciones con `rtree_index.intersection(mbr, objects=True)`
4. Se verifica cada candidato para confirmar coincidencia exacta comparando cada coordenada con tolerancia epsilon
5. Se retornan los registros que coinciden exactamente

Se usa una tolerancia pequeña (1e-9) para manejar imprecisiones de floats en las comparaciones.

#### Algoritmo de K-NN
La búsqueda KNN encuentra los k puntos más cercanos a un punto de consulta:

**Proceso:**
1. Se valida que el punto tenga las dimensiones correctas
2. Se utiliza el método `rtree_index.nearest(point, k)` que implementa internamente un algoritmo best-first search
3. La biblioteca rtree utiliza una cola de prioridad ordenada por distancia mínima
4. Se retornan los k vecinos más cercanos con sus claves primarias, ordenados por proximidad

Este enfoque tiene varias ventajas:
- No requiere calcular distancia a todos los puntos (O(k log n) vs O(n) fuerza bruta)
- No necesita conocer el radio de búsqueda de antemano
- Aprovecha la localidad espacial del R-Tree para podar ramas lejanas

#### Análisis de Complejidad
| Operación | Mejor Caso | Caso Promedio | Peor Caso | Observaciones |
|-----------|------------|---------------|-----------|---------------|
| **Inserción** | O(log n) | O(log n) | O(n) | Logarítmico con buen balanceo. Degrada con división de nodos en cascada. |
| **Búsqueda Exacta** | O(log n) | O(log n) | O(n) | Búsqueda por MBR más verificación exacta. Degrada con alto overlap. |
| **Range Search** | O(log n + r) | O(log n + r) | O(n) | r = resultados. Eficiente para rangos pequeños. |
| **KNN** | O(k log n) | O(k log n) | O(n) | Best-first search. Es mejor que fuerza bruta O(n log n). |
| **Eliminación** | O(log n) | O(log n) | O(n) | Incluye posible rebalanceo. |

### Comparación Teórica de Técnicas

| Técnica | Inserción | Búsqueda | Eliminación | Búsqueda por Rango |
|---------|-----------|----------|-------------|-------------------|
| Sequential File | | | | |
| ISAM | | | | |
| Extendible Hash | | | | N/A |
| B+ Tree (Clustered) | | | | |
| B+ Tree (Unclustered) | | | | |
| R-Tree | | | | |

---

## 3. Parser SQL

### Gramática SQL en formato EBNF

```ebnf
statement = create_statement | select_statement | insert_statement | delete_statement ;

create_statement = create_table_statement | create_table_from_file_statement ;

create_table_statement = "CREATE" "TABLE" ID "(" column_definition { "," column_definition } ")" ";" ;

create_table_from_file_statement = "CREATE" "TABLE" ID "FROM" "FILE" STRING 
                                   "USING" [ "PRIMARY" ] "INDEX" index_type "(" ID ")" 
                                   { "," "INDEX" index_type "(" ID ")" } ";" ;

column_definition = ID data_type [ "KEY" ] [ "INDEX" index_type ] ;

data_type = "INT" | "FLOAT" | "DATE" | "VARCHAR" "[" INTEGER "]" | "ARRAY" "[" INTEGER "]" "[" base_data_type "]" ;

base_data_type = "INT" | "FLOAT" | "DATE" ;

index_type = "SEQ" | "BTREE" | "HASH" | "ISAM" | "RTREE" ;

select_statement = "SELECT" column_list "FROM" ID [ where_clause ] [ order_clause ] [ limit_clause ] ";" ;

column_list = "*" | ID { "," ID } ;

where_clause = "WHERE" condition ;

order_clause = "ORDER" "BY" ID [ "ASC" | "DESC" ] ;

limit_clause = "LIMIT" INTEGER ;

insert_statement = "INSERT" "INTO" ID "VALUES" "(" value { "," value } ")" ";" ;

delete_statement = "DELETE" "FROM" ID [ where_clause ] ";" ;

condition = or_condition ;

or_condition = and_condition { "OR" and_condition } ;

and_condition = basic_condition { "AND" basic_condition } ;

basic_condition = "(" condition ")" | comparison_condition | between_condition | spatial_in_condition | spatial_knn_condition ;

comparison_condition = ID ( "=" | "!=" | "<" | "<=" | ">" | ">=" ) value ;

between_condition = ID "BETWEEN" value "AND" value ;

spatial_in_condition = ID "IN" "(" point "," number ")" ;

spatial_knn_condition = ID "KNN" "(" point "," INTEGER ")" ;

value = INTEGER | FLOAT | STRING | "(" number_or_string { "," number_or_string } ")" | "[" number_or_string { "," number_or_string } "]" ;

point = "(" number { "," number } ")" ;

number_or_string = INTEGER | FLOAT | STRING ;

number = INTEGER | FLOAT ;
```

## Ejemplos de Consultas

```sql
-- Crear tabla desde archivo CSV con índice primario y secundarios
CREATE TABLE Restaurantes FROM FILE "restaurantes.csv" 
USING PRIMARY INDEX ISAM(id), INDEX BTREE(nombre), INDEX RTREE(ubicacion);

-- Búsqueda específica
SELECT * FROM Restaurantes WHERE id = 100;

-- Búsqueda por rango
SELECT * FROM Restaurantes WHERE nombre BETWEEN "A" AND "M";

-- Inserción de registros
INSERT INTO Restaurantes VALUES (1, "Pizza Hut", "2024-01-15", (12.5, -77.3));

-- Eliminación de registros
DELETE FROM Restaurantes WHERE id = 50;

-- Búsqueda espacial: punto en radio
SELECT * FROM Restaurantes WHERE ubicacion IN ((12.0, -77.0), 5.0);

-- Búsqueda espacial: K vecinos más cercanos
SELECT * FROM Restaurantes WHERE ubicacion KNN ((12.0, -77.0), 10);
```


---

## 4. Resultados Experimentales

### Configuración de Pruebas

#### Dataset Utilizado

#### Métricas de Evaluación
- Tiempo de ejecución en milisegundos

### Resultados de Inserción

#### Gráfico Comparativo

#### Tabla de Resultados

| Técnica | N=1K (ms) | N=10K (ms) | N=100K (ms) |
|---------|-----------|------------|-------------|
| Sequential File | | | |
| ISAM | | | |
| Extendible Hash | | | |
| B+ Tree (Clustered) | | | |
| B+ Tree (Unclustered) | | | |
| R-Tree | | | |

### Resultados de Búsqueda

#### Gráfico Comparativo

#### Tabla de Resultados

| Técnica | N=1K (ms) | N=10K (ms) | N=100K (ms) |
|---------|-----------|------------|-------------|
| Sequential File | | | |
| ISAM | | | |
| Extendible Hash | | | |
| B+ Tree (Clustered) | | | |
| B+ Tree (Unclustered) | | | |
| R-Tree | | | |

### Resultados de Búsqueda por Rango

#### Gráfico Comparativo

#### Tabla de Resultados

| Técnica | N=1K (ms) | N=10K (ms) | N=100K (ms) |
|---------|-----------|------------|-------------|
| Sequential File | | | |
| ISAM | | | |
| Extendible Hash | - | - | - |
| B+ Tree (Clustered) | | | |
| B+ Tree (Unclustered) | | | |
| R-Tree | | | |

### Resultados de Eliminación

#### Gráfico Comparativo

#### Tabla de Resultados

| Técnica | N=1K (ms) | N=10K (ms) | N=100K (ms) |
|---------|-----------|------------|-------------|
| Sequential File | | | |
| ISAM | | | |
| Extendible Hash | | | |
| B+ Tree (Clustered) | | | |
| B+ Tree (Unclustered) | | | |
| R-Tree | | | |

### Análisis y Discusión

---

## 5. Pruebas de Uso

### Interfaz Gráfica

#### Funcionalidades del Frontend

- Creación de tablas desde archivo CSV
- Selección de índices (primario y secundarios)
- Ejecución de consultas SQL
- Visualización de resultados en tablas
- Filtrado y búsqueda de datos
- Operaciones CRUD (Create, Read, Update, Delete)
- Búsquedas espaciales (IN, KNN)
- Métricas de rendimiento en tiempo real


---

## 🎥 Video de Demostración

[Enlace al video explicativo](#)

---

## 🚀 Despliegue con Docker

```bash
# Clonar el repositorio
git clone https://github.com/joaquinsalinas06/Proyecto-1-BD2
cd Proyecto-1-BD2

# Levantar los servicios
docker-compose up --build
```

**Acceso al sistema:**
- 🖥️ **Frontend (UI)**: http://localhost:3000
- 🔌 **API REST**: http://localhost:8000
- 📖 **Documentación API**: http://localhost:8000/docs

---

## 👥 Integrantes

- Joaquin Mauricio Salinas Salas
- Isaac Emanuel Javier Simeon Sarmiento
- Nayeli Fernanda Guzman Huayta
- Renzo Josimar Felix Apointe