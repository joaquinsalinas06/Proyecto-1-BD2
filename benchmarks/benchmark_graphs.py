import os
import pandas as pd
import matplotlib.pyplot as plt

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def save_bar(df, index_col, title, path, figsize=(10,6), ylabel="Cantidad de I/O"):
    df_plot = df.set_index(index_col)
    df_plot.plot(kind="bar", figsize=figsize)
    plt.title(title)
    plt.ylabel(ylabel)
    plt.xlabel(index_col)
    plt.legend(bbox_to_anchor=(1.05, 1), loc="upper left")
    plt.tight_layout()
    plt.savefig(path, dpi=300)
    plt.close()

def save_line(df, index_col, cols, title, path, logy=False, marker='o', figsize=(8,5)):
    df_plot = df.set_index(index_col)
    df_plot[cols].plot(marker=marker, figsize=figsize, logy=logy)
    plt.title(title)
    plt.ylabel("Operaciones I/O" + (" (log)" if logy else ""))
    plt.xlabel(index_col)
    plt.tight_layout()
    plt.savefig(path, dpi=300)
    plt.close()

def total_io_df(df, index_col, exclude_cols=None):
    if exclude_cols is None: exclude_cols = []
    cols = [c for c in df.columns if c != index_col and c not in exclude_cols]
    return pd.DataFrame({index_col: df[index_col], "Total I/O": df[cols].sum(axis=1)})

juegos_dir = os.path.join("graficos", "juegos")
ensure_dir(juegos_dir)

df_seq = pd.DataFrame({
    "Tamaño": ["1K", "10K", "100K"],
    "Bulk Load I/O": [900, 9000, 90000],
    "Insert I/O": [21099, 126835, 1080778],
    "PK Exact I/O": [127, 248, 225],
    "Hash I/O": [460, 855, 788],
    "Publisher I/O": [10000, 91000, 901000],
    "Price Range I/O": [5000, 45500, 450500],
    "PK Range I/O": [796, 6586, 59022],
    "Positive I/O": [3000, 27300, 270300],
    "Delete I/O": [39846, 363916, 3603970]
})

df_btree = pd.DataFrame({
    "Tamaño": ["1K", "10K", "100K"],
    "Bulk Load I/O": [16, 142, 1424],
    "Insert I/O": [314, 414, 498],
    "PK Exact I/O": [20, 20, 30],
    "Hash I/O": [70, 70, 105],
    "Publisher I/O": [170, 1300, 7570],
    "Price Range I/O": [85, 650, 3785],
    "PK Range I/O": [85, 650, 3785],
    "Positive I/O": [51, 390, 2271],
    "Delete I/O": [179, 180, 262]
})

df_isam = pd.DataFrame({
    "Tamaño": ["1K", "10K", "100K"],
    "Bulk Load I/O": [200, 494, 2463],
    "Insert I/O": [800, 800, 975],
    "PK Exact I/O": [81, 64, 99],
    "Hash I/O": [286, 214, 246],
    "Publisher I/O": [1890, 3150, 11350],
    "Price Range I/O": [945, 1575, 5675],
    "PK Range I/O": [152, 242, 771],
    "Positive I/O": [567, 945, 3405],
    "Delete I/O": [356, 313, 453]
})

save_bar(df_seq, "Tamaño", "Sequential File + Hash Index (Juegos)", os.path.join(juegos_dir, "sequential_hash.png"))
save_bar(df_btree, "Tamaño", "B+Tree + Hash Index (Juegos)", os.path.join(juegos_dir, "bptree_hash.png"))
save_bar(df_isam, "Tamaño", "ISAM + Hash Index (Juegos)", os.path.join(juegos_dir, "isam_hash.png"))

total_juegos = pd.DataFrame({
    "Tamaño": df_seq["Tamaño"],
    "Sequential File": df_seq.drop(columns="Tamaño").sum(axis=1),
    "B+Tree": df_btree.drop(columns="Tamaño").sum(axis=1),
    "ISAM": df_isam.drop(columns="Tamaño").sum(axis=1)
})
save_bar(total_juegos, "Tamaño", "Comparativa Total de I/O (Juegos)", os.path.join(juegos_dir, "comparativa_general.png"))
save_line(total_juegos, "Tamaño", ["Sequential File", "B+Tree", "ISAM"], "Tendencia Total de I/O (Juegos)", os.path.join(juegos_dir, "io_tendencia_lineal.png"), logy=False)
save_line(total_juegos, "Tamaño", ["Sequential File", "B+Tree", "ISAM"], "Tendencia Logarítmica de I/O (Juegos)", os.path.join(juegos_dir, "io_tendencia_log.png"), logy=True)

airbnb_dir = os.path.join("graficos", "airbnb")
ensure_dir(airbnb_dir)

df_seq_airbnb = pd.DataFrame({
    "Tamaño": ["1K", "10K", "100K"],
    "Insert I/O": [21099, 119804, 804958],
    "Exact Search I/O": [131, 189, 227],
    "Spatial IN I/O": [74239, 563111, 655985],
    "Spatial KNN I/O": [1392, 1975, 2311],
    "City Query I/O": [1000, 7527, 67115],
    "Price Range I/O": [5000, 37635, 335575],
    "PK Range I/O": [195, 177, 319],
    "Room Type Query I/O": [2000, 15054, 134230],
    "Delete I/O": [39840, 300978, 2684562]
})

df_btree_airbnb = pd.DataFrame({
    "Tamaño": ["1K", "10K", "100K"],
    "Insert I/O": [302, 306, 410],
    "Exact Search I/O": [20, 20, 30],
    "Spatial IN I/O": [11428, 59510, 89265],
    "Spatial KNN I/O": [210, 210, 315],
    "City Query I/O": [11, 64, 535],
    "Price Range I/O": [55, 320, 2675],
    "PK Range I/O": [55, 320, 2675],
    "Room Type Query I/O": [22, 128, 1070],
    "Delete I/O": [161, 180, 273]
})

df_isam_airbnb = pd.DataFrame({
    "Tamaño": ["1K", "10K", "100K"],
    "Insert I/O": [772, 800, 1000],
    "Exact Search I/O": [273, 340, 450],
    "Spatial IN I/O": [58050, 201920, 217051],
    "Spatial KNN I/O": [924, 787, 735],
    "City Query I/O": [161, 279, 890],
    "Price Range I/O": [805, 1395, 4450],
    "PK Range I/O": [55, 25, 76],
    "Room Type Query I/O": [322, 558, 1780],
    "Delete I/O": [1778, 1022, 1978]
})

save_bar(df_seq_airbnb, "Tamaño", "Sequential File + R-Tree Index (Airbnb)", os.path.join(airbnb_dir, "sequential_rtree.png"))
save_bar(df_btree_airbnb, "Tamaño", "B+Tree + R-Tree Index (Airbnb)", os.path.join(airbnb_dir, "bptree_rtree.png"))
save_bar(df_isam_airbnb, "Tamaño", "ISAM + R-Tree Index (Airbnb)", os.path.join(airbnb_dir, "isam_rtree.png"))

exclude_spatial = ["Spatial IN I/O", "Spatial KNN I/O"]
total_airbnb_general = pd.DataFrame({
    "Tamaño": df_seq_airbnb["Tamaño"],
    "Sequential File": df_seq_airbnb.drop(columns=["Tamaño"] + exclude_spatial).sum(axis=1),
    "B+Tree": df_btree_airbnb.drop(columns=["Tamaño"] + exclude_spatial).sum(axis=1),
    "ISAM": df_isam_airbnb.drop(columns=["Tamaño"] + exclude_spatial).sum(axis=1)
})
save_bar(total_airbnb_general, "Tamaño", "Comparativa Total de I/O (Airbnb) - Sin Spatial", os.path.join(airbnb_dir, "comparativa_general.png"))
save_line(total_airbnb_general, "Tamaño", ["Sequential File", "B+Tree", "ISAM"], "Tendencia Total de I/O (Airbnb) - Sin Spatial", os.path.join(airbnb_dir, "io_tendencia_lineal.png"), logy=False)
save_line(total_airbnb_general, "Tamaño", ["Sequential File", "B+Tree", "ISAM"], "Tendencia Logarítmica de I/O (Airbnb) - Sin Spatial", os.path.join(airbnb_dir, "io_tendencia_log.png"), logy=True)

spatial_df = pd.DataFrame({
    "Tamaño": df_seq_airbnb["Tamaño"],
    "Sequential Spatial IN": df_seq_airbnb["Spatial IN I/O"],
    "Sequential Spatial KNN": df_seq_airbnb["Spatial KNN I/O"],
    "BTree Spatial IN": df_btree_airbnb["Spatial IN I/O"],
    "BTree Spatial KNN": df_btree_airbnb["Spatial KNN I/O"],
    "ISAM Spatial IN": df_isam_airbnb["Spatial IN I/O"],
    "ISAM Spatial KNN": df_isam_airbnb["Spatial KNN I/O"]
})

spatial_in = spatial_df[["Tamaño", "Sequential Spatial IN", "BTree Spatial IN", "ISAM Spatial IN"]]
spatial_knn = spatial_df[["Tamaño", "Sequential Spatial KNN", "BTree Spatial KNN", "ISAM Spatial KNN"]]
save_bar(spatial_in, "Tamaño", "Comparativa Spatial IN (Airbnb)", os.path.join(airbnb_dir, "comparativa_spatial_in.png"))
save_bar(spatial_knn, "Tamaño", "Comparativa Spatial KNN (Airbnb)", os.path.join(airbnb_dir, "comparativa_spatial_knn.png"))

total_juegos_all = pd.DataFrame({
    "Tamaño": df_seq["Tamaño"],
    "Sequential File": df_seq.drop(columns="Tamaño").sum(axis=1),
    "B+Tree": df_btree.drop(columns="Tamaño").sum(axis=1),
    "ISAM": df_isam.drop(columns="Tamaño").sum(axis=1)
})
save_bar(total_juegos_all, "Tamaño", "Total I/O (Juegos) - Todos los campos", os.path.join(juegos_dir, "io_total_all.png"))

total_airbnb_all = pd.DataFrame({
    "Tamaño": df_seq_airbnb["Tamaño"],
    "Sequential File": df_seq_airbnb.drop(columns="Tamaño").sum(axis=1),
    "B+Tree": df_btree_airbnb.drop(columns="Tamaño").sum(axis=1),
    "ISAM": df_isam_airbnb.drop(columns="Tamaño").sum(axis=1)
})
save_bar(total_airbnb_all, "Tamaño", "Total I/O (Airbnb) - Todos los campos", os.path.join(airbnb_dir, "io_total_all.png"))

print("Gráficos guardados en 'graficos/juegos' y 'graficos/airbnb'")
