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

#### Algoritmo de Inserción

#### Algoritmo de Búsqueda

#### Algoritmo de Búsqueda por Rango

#### Algoritmo de Eliminación

#### Análisis de Complejidad

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

#### Algoritmo de Inserción

#### Algoritmo de Búsqueda Espacial

#### Algoritmo de K-NN

#### Análisis de Complejidad

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