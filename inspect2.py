import openpyxl
files = {
 "曝光频次":"/Users/panjinlong/Downloads/AMCExploration_W81K曝光频次.xlsx",
 "分时情况":"/Users/panjinlong/Downloads/AMCExploration_W81K分时情况.xlsx",
}
for name,path in files.items():
    print("\n\n############", name, "############")
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    for ws in wb.worksheets:
        print(f"\n=== SHEET: {ws.title} ===")
        rows = list(ws.iter_rows(values_only=True))
        # print header-ish: first 4 rows with col index
        for ri,r in enumerate(rows[:5]):
            print(f"row{ri}:")
            for ci,v in enumerate(r):
                if v is not None:
                    print(f"   c{ci}: {v!r}")
        print(f"... total rows={len(rows)}")
        # print a few data rows in full
        print("--- sample data rows (with col idx) ---")
        for ri in range(4, min(8, len(rows))):
            r=rows[ri]
            print(f"row{ri}:")
            for ci,v in enumerate(r):
                if v is not None:
                    print(f"   c{ci}: {v!r}")
