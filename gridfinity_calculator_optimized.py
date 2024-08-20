import streamlit as st
import numpy as np
import matplotlib.pyplot as plt

# Function to convert inches to millimeters if needed
def convert_to_mm(value, units):
    if units == "Inches":
        return value * 25.4
    return value

def calculate_baseplates(printer_x, printer_y, space_x, space_y, grid_size=42):
    total_units_x = space_x / grid_size
    total_units_y = space_y / grid_size

    max_units_x = printer_x / grid_size
    max_units_y = printer_y / grid_size

    # Convert to integer only when creating the layout grid
    layout = np.zeros((int(total_units_y), int(total_units_x)), dtype=int)
    bill_of_materials = {}

    color_index = 1

    # Step 1: Fill the grid with the largest possible baseplates
    for y in range(0, int(total_units_y), int(max_units_y)):
        for x in range(0, int(total_units_x), int(max_units_x)):
            baseplate_x = min(int(max_units_x), int(total_units_x) - x)
            baseplate_y = min(int(max_units_y), int(total_units_y) - y)

            # Detect if the last row or column will result in a 1x unit
            if (int(total_units_x) - x == 1 and x > 0) or (int(total_units_y) - y == 1 and y > 0):
                if int(total_units_x) - x == 1:
                    layout[y:y + baseplate_y, x - 1:x + 1] = color_index
                elif int(total_units_y) - y == 1:
                    layout[y - 1:y + 1, x:x + baseplate_x] = color_index
                color_index += 1
            else:
                layout[y:y + baseplate_y, x:x + baseplate_x] = color_index
                color_index += 1

    # Step 2: Accurately count the sizes in the bill of materials
    for color in range(1, color_index):
        ys, xs = np.where(layout == color)
        if len(xs) > 0 and len(ys) > 0:
            width = xs.max() - xs.min() + 1
            height = ys.max() - ys.min() + 1
            size_key = f"{width}x{height}"
            if size_key in bill_of_materials:
                bill_of_materials[size_key] += 1
            else:
                bill_of_materials[size_key] = 1

    leftover_x = round(space_x - int(total_units_x) * grid_size, 1)
    leftover_y = round(space_y - int(total_units_y) * grid_size, 1)

    return layout, bill_of_materials, leftover_x, leftover_y, int(total_units_x), int(total_units_y), int(max_units_x), int(max_units_y)

st.title("Gridfinity Baseplate Layout Calculator - Optimized to Avoid Any 1x Dimension Baseplates")

# Dropdowns for units selection
printer_units = st.selectbox("Select Printer Dimensions Units:", ["Millimeters", "Inches"])
space_units = st.selectbox("Select Area Dimensions Units:", ["Millimeters", "Inches"])

# Inputs with updated labels
printer_x = st.number_input(f"Printer Max Build Size X ({printer_units}):", value=227 if printer_units == "Millimeters" else 8.94)
printer_y = st.number_input(f"Printer Max Build Size Y ({printer_units}):", value=255 if printer_units == "Millimeters" else 10.04)
space_x = st.number_input(f"Enter the space's X dimension you want to fill ({space_units}):", value=1000 if space_units == "Millimeters" else 39.37)
space_y = st.number_input(f"Enter the space's Y dimension you want to fill ({space_units}):", value=800 if space_units == "Millimeters" else 31.5)

# Convert to millimeters if needed
printer_x_mm = convert_to_mm(printer_x, printer_units)
printer_y_mm = convert_to_mm(printer_y, printer_units)
space_x_mm = convert_to_mm(space_x, space_units)
space_y_mm = convert_to_mm(space_y, space_units)

if st.button("Calculate Layout"):
    layout, bill_of_materials, leftover_x, leftover_y, total_units_x, total_units_y, max_units_x, max_units_y = calculate_baseplates(printer_x_mm, printer_y_mm, space_x_mm, space_y_mm)

    st.write(f"Total Fill Area Gridfinity units (X x Y): {total_units_x} x {total_units_y}")
    st.write(f"Leftover X distance: {leftover_x} mm")
    st.write(f"Leftover Y distance: {leftover_y} mm")
    
    max_plate_size = f"{max_units_x}x{max_units_y} Gridfinity units"
    st.write(f"Maximum Plate Size Your Printer Can Handle: {max_plate_size}")

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
