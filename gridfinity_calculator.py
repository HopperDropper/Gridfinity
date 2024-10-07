import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import io
from enum import Enum
from jinja2 import Template

UNITS = ["Millimeters", "Inches"]

# Function to convert inches to millimeters if needed
def convert_to_mm(value, units):
    if units == "Inches":
        return value * 25.4
    return value

def build_plate_matrix(total_units_x, total_units_y, max_units_x, max_units_y):
    plate_matrix = np.zeros((total_units_y, total_units_x), dtype=int)
    plate_counter = 1

    for y in range(0, total_units_y, max_units_y):
        for x in range(0, total_units_x, max_units_x):
            plate_x = min(max_units_x, total_units_x - x)
            plate_y = min(max_units_y, total_units_y - y)

            # Prevent the last row/column from being a 1x dimension
            if plate_x == 1 and x > 0:
                plate_matrix[y:y + plate_y, x - 1:x + 1] = plate_counter
            elif plate_y == 1 and y > 0:
                plate_matrix[y - 1:y + 1, x:x + plate_x] = plate_counter
            else:
                plate_matrix[y:y + plate_y, x:x + plate_x] = plate_counter

            plate_counter += 1

    return plate_matrix, plate_counter - 1

def determine_padding(plate_matrix, leftover_x, leftover_y, padding_option):
    y, x = plate_matrix.shape
    unique_plates = np.unique(plate_matrix)
    bill_of_materials_with_padding = {}

    for plate in unique_plates:
        if plate == 0:
            continue

        # Find the bounding box of this plate
        rows, cols = np.where(plate_matrix == plate)
        min_row, max_row = rows.min(), rows.max()
        min_col, max_col = cols.min(), cols.max()

        plate_x = max_col - min_col + 1
        plate_y = max_row - min_row + 1

        padding_info = []
        fitx, fity = 0, 0
        if padding_option == "Corner Justify":
            if max_col == x - 1 and leftover_x > 0:  # Rightmost plate
                padding_info.append(f"{round(leftover_x, 1)}mm Right")
                fitx = 1
            if max_row == y - 1 and leftover_y > 0:  # Topmost plate
                padding_info.append(f"{round(leftover_y, 1)}mm Top")
                fity = 1
        elif padding_option == "Center Justify":
            if min_col == 0 and leftover_x > 0:  # Leftmost plate
                padding_info.append(f"{round(leftover_x / 2, 1)}mm Left")
                fitx = -1
            if max_col == x - 1 and leftover_x > 0:  # Rightmost plate
                padding_info.append(f"{round(leftover_x / 2, 1)}mm Right")
                fitx = 1
            if min_row == 0 and leftover_y > 0:  # Bottommost plate
                padding_info.append(f"{round(leftover_y / 2, 1)}mm Bottom")
                fity = -1
            if max_row == y - 1 and leftover_y > 0:  # Topmost plate
                padding_info.append(f"{round(leftover_y / 2, 1)}mm Top")
                fity = 1

        plate_key = f"{plate_x}x{plate_y}"
        if padding_info:
            plate_key += f" ({', '.join(padding_info)})"

        if plate_key in bill_of_materials_with_padding:
            bill_of_materials_with_padding[plate_key] += 1
        else:
            bill_of_materials_with_padding[plate_key] = 1

    return bill_of_materials_with_padding

def calculate_baseplates(printer_x, printer_y, space_x, space_y, grid_size=42):
    total_units_x = int(space_x // grid_size)
    total_units_y = int(space_y // grid_size)

    max_units_x = int(printer_x // grid_size)
    max_units_y = int(printer_y // grid_size)

    layout = np.zeros((total_units_y, total_units_x), dtype=int)

    plate_matrix, _ = build_plate_matrix(total_units_x, total_units_y, max_units_x, max_units_y)

    leftover_x = space_x - total_units_x * grid_size
    leftover_y = space_y - total_units_y * grid_size

    return plate_matrix, leftover_x, leftover_y, total_units_x, total_units_y, max_units_x, max_units_y

def summarize_bom(plate_matrix):
    y, x = plate_matrix.shape
    unique_plates = np.unique(plate_matrix)
    bill_of_materials = {}

    for plate in unique_plates:
        if plate == 0:
            continue

        rows, cols = np.where(plate_matrix == plate)
        min_row, max_row = rows.min(), rows.max()
        min_col, max_col = cols.min(), cols.max()

        plate_x = max_col - min_col + 1
        plate_y = max_row - min_row + 1

        plate_key = f"{plate_x}x{plate_y}"
        if plate_key in bill_of_materials:
            bill_of_materials[plate_key] += 1
        else:
            bill_of_materials[plate_key] = 1

    return bill_of_materials

def generate_openscad_code(gridx: int, gridy: int, padding_x: int=0, padding_y: int=0, fitx: int=0, fity: int=0):
    with open("baseplate.scad.j2", "r") as f:
        scad_template = Template(str(f.read()))

    return scad_template.render(grid_x=gridx,
                                grid_y=gridy,
                                padding_x=padding_x,
                                padding_y=padding_y,
                                fit_x=fitx,
                                fit_y=fity)

st.title("Gridfinity Baseplate Layout Calculator - Optimized to Avoid Any 1x Dimension Baseplates")

# Dropdowns for units selection
printer_units = st.selectbox("Select Printer Dimensions Units:", options=UNITS)
space_units = st.selectbox("Select Area Dimensions Units:", options=UNITS, )

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

# Padding option dropdown
padding_option = st.selectbox("Select Padding Calculation Option:", ["Corner Justify", "Center Justify", "No Padding Calculation"])

if st.button("Calculate Layout"):
    layout, leftover_x, leftover_y, total_units_x, total_units_y, max_units_x, max_units_y = calculate_baseplates(printer_x_mm, printer_y_mm, space_x_mm, space_y_mm)

    # Store results in session state
    st.session_state.layout = layout
    st.session_state.leftover_x = leftover_x
    st.session_state.leftover_y = leftover_y
    st.session_state.total_units_x = total_units_x
    st.session_state.total_units_y = total_units_y

    # Display results
    st.write(f"Total Fill Area Gridfinity units (X x Y): {total_units_x} x {total_units_y}")
    st.write(f"Leftover X distance: {round(leftover_x, 1)} mm")
    st.write(f"Leftover Y distance: {round(leftover_y, 1)} mm")
    max_plate_size = f"{max_units_x}x{max_units_y} Gridfinity units"
    st.write(f"Maximum Plate Size Your Printer Can Handle: {max_plate_size}")

if 'layout' in st.session_state:
    layout = st.session_state.layout
    leftover_x = st.session_state.leftover_x
    leftover_y = st.session_state.leftover_y
    total_units_x = st.session_state.total_units_x
    total_units_y = st.session_state.total_units_y

    if padding_option != "No Padding Calculation":
        bill_of_materials_with_padding = determine_padding(layout, leftover_x, leftover_y, padding_option)
        st.write("Bill of Materials with Padding:")

        for size, quantity in bill_of_materials_with_padding.items():
            st.write(f"{quantity} x {size}")
            size_part = size.split(' ')[0]
            gridx, gridy = map(int, size_part.split('x'))

            # Extract padding based on size
            if padding_option == "Corner Justify":
                padding_x = leftover_x if 'Right' in size else 0
                padding_y = leftover_y if 'Top' in size else 0
                fitx, fity = 0, 0
                if 'Left' in size:
                    fitx = -1
                elif 'Right' in size:
                    fitx = 1
                if 'Bottom' in size:
                    fity = -1
                elif 'Top' in size:
                    fity = 1

            elif padding_option == "Center Justify":
                # Center Justify: split padding equally between both sides
                padding_x = leftover_x / 2
                padding_y = leftover_y / 2
                fitx, fity = 0, 0
                if 'Left' in size and 'Right' in size:
                    fitx = 0  # Center padding
                elif 'Left' in size:
                    fitx = -1
                elif 'Right' in size:
                    fitx = 1

                # Adjust fity based on top/bottom padding
                if 'Top' in size and 'Bottom' in size:
                    fity = 0  # Center padding
                elif 'Bottom' in size:
                    fity = -1
                elif 'Top' in size:
                    fity = 1

            # Download button
            scad_code = generate_openscad_code(gridx, gridy, padding_x, padding_y, fitx, fity)
            buffer = io.BytesIO()
            buffer.write(scad_code.encode())
            buffer.seek(0)

            st.download_button(
                label=f"Download OpenSCAD Code for {size}",
                data=buffer,
                file_name=f"OpenSCAD_Code_{size.replace(' ', '_')}.scad",
                mime="text/plain"
            )

    else:
        # Summarize the plates without padding
        bill_of_materials = summarize_bom(layout)
        st.write("Bill of Materials:")
        for size, quantity in bill_of_materials.items():
            st.write(f"{quantity} x {size}")

            size_part = size.split(' ')[0]
            gridx, gridy = map(int, size_part.split('x'))

            # Download button
            scad_code = generate_openscad_code(gridx, gridy)
            buffer = io.BytesIO()
            buffer.write(scad_code.encode())
            buffer.seek(0)

            st.download_button(
                label=f"Download OpenSCAD Code for {size}",
                data=buffer,
                file_name=f"OpenSCAD_Code_{size.replace(' ', '_')}.scad",
                mime="text/plain"
            )

    # Plotting section
    fig, ax = plt.subplots()

    # Plot the leftover space in grey
    ax.add_patch(plt.Rectangle((0, 0), space_x_mm, space_y_mm, edgecolor='black', facecolor='lightgrey', lw=2))

    # Plot the layout on top of the grey background
    ax.imshow(layout, cmap='tab20', origin='lower', extent=[0, total_units_x * 42, 0, total_units_y * 42], zorder=2)

    # Manually draw the gridlines on top of everything
    for y in np.arange(0, total_units_y * 42 + 42, 42):
        ax.hlines(y, 0, total_units_x * 42, color='white', linewidth=1.5, zorder=4)
    for x in np.arange(0, total_units_x * 42 + 42, 42):
        ax.vlines(x, 0, total_units_y * 42, color='white', linewidth=1.5, zorder=4)

    ax.set_xlim(-leftover_x / 2 if padding_option == "Center Justify" else 0,
                total_units_x * 42 + leftover_x / 2 if padding_option == "Center Justify" else total_units_x * 42 + leftover_x)
    ax.set_ylim(-leftover_y / 2 if padding_option == "Center Justify" else 0,
                total_units_y * 42 + leftover_y / 2 if padding_option == "Center Justify" else total_units_y * 42 + leftover_y)
    ax.set_aspect('equal', adjustable='box')

    st.pyplot(fig)
