import streamlit as st
import numpy as np
import matplotlib.pyplot as plt

def calculate_baseplates(printer_x, printer_y, space_x, space_y, grid_size=42):
    total_units_x = space_x // grid_size
    total_units_y = space_y // grid_size

    max_units_x = printer_x // grid_size
    max_units_y = printer_y // grid_size

    layout = np.zeros((total_units_y, total_units_x), dtype=int)
    bill_of_materials = {}

    color_index = 1
    for start_y in range(0, total_units_y, max_units_y):
        for start_x in range(0, total_units_x, max_units_x):
            baseplate_x = min(max_units_x, total_units_x - start_x)
            baseplate_y = min(max_units_y, total_units_y - start_y)

            layout[start_y:start_y + baseplate_y, start_x:start_x + baseplate_x] = color_index

            size_key = f"{baseplate_x}x{baseplate_y}"
            if size_key in bill_of_materials:
                bill_of_materials[size_key] += 1
            else:
                bill_of_materials[size_key] = 1

            color_index += 1

    leftover_x = space_x - total_units_x * grid_size
    leftover_y = space_y - total_units_y * grid_size

    return layout, bill_of_materials, leftover_x, leftover_y, total_units_x, total_units_y

st.title("Gridfinity Baseplate Layout Calculator")

printer_x = st.number_input("Enter your printer's X dimension (in mm):", value=227)
printer_y = st.number_input("Enter your printer's Y dimension (in mm):", value=255)
space_x = st.number_input("Enter the space's X dimension you want to fill (in mm):", value=323)
space_y = st.number_input("Enter the space's Y dimension you want to fill (in mm):", value=431)

if st.button("Calculate Layout"):
    layout, bill_of_materials, leftover_x, leftover_y, total_units_x, total_units_y = calculate_baseplates(printer_x, printer_y, space_x, space_y)

    st.write(f"Total Gridfinity units (X x Y): {total_units_x} x {total_units_y}")
    st.write(f"Leftover X distance: {leftover_x} mm")
    st.write(f"Leftover Y distance: {leftover_y} mm")

    st.write("Bill of Materials:")
    for size, quantity in bill_of_materials.items():
        st.write(f"{quantity} x {size}")

    fig, ax = plt.subplots()
    ax.imshow(layout, cmap='tab20', origin='lower', extent=[0, total_units_x * 42, 0, total_units_y * 42])
    ax.grid(True, which='both', color='black', linestyle='--', linewidth=0.5)
    ax.set_xticks(np.arange(0, total_units_x * 42 + 42, 42))
    ax.set_yticks(np.arange(0, total_units_y * 42 + 42, 42))
    ax.set_aspect('equal', adjustable='box')
    ax.invert_yaxis()
    st.pyplot(fig)
