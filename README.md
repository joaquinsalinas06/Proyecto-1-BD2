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

# 2.2 ISAM (Indexed Sequential Access Method)

## Introducción

El método **ISAM (Indexed Sequential Access Method)** es una técnica de indexación que combina un acceso **secuencial ordenado** con un **índice jerárquico**. Aunque originalmente fue diseñado como un método **estático**, en esta implementación se extiende para permitir un **crecimiento dinámico del índice** de 2 a 3 niveles según crece el volumen de datos.


---

## Características del ISAM Implementado

*  Índice jerárquico **dinámico** (2 o 3 niveles)
*  Soporta **overflow encadenado** para manejar inserciones
*  Claves **ordenadas** para búsqueda eficiente
*  **Persistencia en disco**, bajo consumo de memoria RAM
*  Soporte para **búsquedas por rango**
*  Operaciones eficientes: **O(log n)** en búsqueda

---

## Estructura General

ISAM organiza los datos en dos archivos principales:

*  **data_file** → almacena páginas de datos
*  **tree_file** → almacena nodos del índice

### Componentes del Índice

| Nivel              | Descripción                            |
| ------------------ | -------------------------------------- |
| Nivel 0            | Páginas de datos (registros ordenados) |
| Nivel 1            | Nodos hoja que apuntan a páginas       |
| Nivel 2            | Nodos intermedios que agrupan hojas    |
| Nivel 3 (opcional) | Raíz cuando los datos son grandes      |

Representación del crecimiento dinámico:

```
2 niveles (pocos datos):        3 niveles (muchos datos):
        ROOT                             ROOT
         │                                │
       Hojas                        Nodos intermedios
         │                                │
      Páginas                         Hojas → Páginas
```


## 2.2.1 Algoritmo de Construcción del Índice

### Objetivo

Organizar los registros iniciales y construir el índice jerárquico para permitir el acceso eficiente mediante búsqueda binaria en cada nivel del árbol.

### Descripción General

El proceso de construcción del índice ISAM se basa en ordenar los registros por su clave primaria y agruparlos en páginas de tamaño fijo. Posteriormente se crean los nodos hoja y nodos intermedios que almacenan únicamente claves guía y punteros hacia páginas o subíndices. En caso de que el volumen de datos supere la capacidad inicial, el índice admite la creación dinámica de un tercer nivel para mantener un acceso eficiente.

### Supuestos de Construcción

* Las claves están ordenadas de manera ascendente.
* Cada página tiene tamaño fijo.
* Si el número de páginas supera la capacidad de un nodo, se forma un nuevo nivel jerárquico.

### Pseudocódigo

Construcción del índice jerárquico inicial:

```
ConstruirIndice(registros):
    ordenar(registros)
    paginas = agruparEnPaginas(registros)
    hojas = crearNodosHoja(paginas)
    while longitud(hojas) > maxClavesPorNodo:
        hojas = agruparEnNodosSuperiores(hojas)
    raiz = crearNodoRaiz(hojas)
    return raiz
```

---

## 2.2.2 Algoritmo de Inserción

La inserción en ISAM permite agregar nuevos registros manteniendo el orden lógico del archivo sin necesidad de reorganizar las páginas existentes. Para conservar la eficiencia del índice, se emplea una política de manejo de desbordamiento mediante páginas encadenadas.

Pasos principales:

1. Localizar la hoja adecuada mediante navegación en el índice.
2. Leer la página de datos correspondiente.
3. Insertar ordenadamente si la página tiene espacio disponible.
4. Utilizar una página de desbordamiento si la página está completa.
5. Actualizar los metadatos del índice.

Pseudocódigo:

```
ISAM_Insert(key, record):
    if not is_built:
        build([record])
        return True

    current = root_pointer
    while current is not Leaf:
        node = read_node(current)
        index = binary_search(node.values, key)
        current = node.pointers[index]

    leaf = read_node(current)
    page = read_page(leaf.data_page_pointer)

    if len(page.records) < BLOCK_FACTOR:
        page.records.append(record)
        page.records.sort()
        write_page(page)
    else:
        overflow_pos = write_overflow(record)
        if page.overflow_pointer == -1:
            page.overflow_pointer = overflow_pos
            write_page(page)

    num_records++
    save_metadata()
```

---

## 2.2.3 Algoritmo de Búsqueda

La búsqueda en ISAM se realiza mediante navegación jerárquica en el índice y búsqueda binaria en las páginas de datos. El algoritmo incluye la verificación de registros adicionales almacenados en páginas de desbordamiento.

Pseudocódigo:

```
ISAM_Search(key):
    leaf = find_leaf(key)
    if leaf is NULL:
        return []

    page = read_page(leaf.data_page_pointer)
    results = binary_search_all(page.records, key)

    if page.overflow_pointer != -1:
        overflow_records = read_overflow(page.overflow_pointer)
        for r in overflow_records:
            if r.key == key:
                results.append(r)

    return results
```

---

## 2.2.4 Algoritmo de Búsqueda por Rango

La búsqueda por rango permite recuperar todos los registros cuyas claves se encuentren entre dos valores determinados. Este algoritmo aprovecha el ordenamiento secuencial de las páginas de datos enlazadas.

Pseudocódigo:

```
ISAM_RangeSearch(begin_key, end_key):
    results = []
    leaf = find_leaf(begin_key)

    while leaf is not NULL:
        page = read_page(leaf.data_page_pointer)

        for record in page.records:
            if begin_key <= record.key <= end_key:
                results.append(record)
            if record.key > end_key:
                return results

        if page.overflow_pointer != -1:
            overflow_records = read_overflow(page.overflow_pointer)
            for r in overflow_records:
                if begin_key <= r.key <= end_key:
                    results.append(r)

        leaf = read_node(leaf.next_pointer)

    return results
```

---

## 2.2.5 Algoritmo de Eliminación

La eliminación consiste en localizar y remover todos los registros que coincidan con una clave dada, tanto en la página principal como en su cadena de overflow.

Pseudocódigo:

```
ISAM_Delete(key):
    leaf = find_leaf(key)
    if leaf is NULL:
        return False

    page = read_page(leaf.data_page_pointer)
    page.records = [r for r in page.records if r.key != key]

    if page.overflow_pointer != -1:
        overflow = read_overflow(page.overflow_pointer)
        filtered = [r for r in overflow if r.key != key]
        rebuild_overflow(filtered)

    write_page(page)
    num_records--
    save_metadata()
    return True
```

---

## 2.2.6 Análisis de Complejidad

El rendimiento del método ISAM se resume en términos de tiempo de ejecución y espacio en disco empleado.

| Operación          | Complejidad Temporal |
| ------------------ | -------------------- |
| Construcción       | O(n log n)           |
| Inserción          | O(log n)             |
| Búsqueda           | O(log n + k)         |
| Búsqueda por rango | O(log n + r + k)     |
| Eliminación        | O(log n + k)         |

Donde:

* n = número total de registros
* r = número de resultados devueltos
* k = registros almacenados en páginas de desbordamiento

---


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