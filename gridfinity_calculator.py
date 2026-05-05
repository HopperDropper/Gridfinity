import io
import zipfile

import matplotlib.pyplot as plt
from matplotlib import patheffects
import numpy as np
import streamlit as st
from jinja2 import Template

UNITS = ["Millimeters", "Inches"]


# Function to convert inches to millimeters if needed
def convert_to_mm(value, units):
    if units == "Inches":
        return value * 25.4
    return value


# Split total units into printable chunks, merging a 1-unit remainder into the previous chunk
def compute_splits(total, max_chunk):
    chunks = []
    remaining = total
    while remaining > 0:
        chunk = min(max_chunk, remaining)
        chunks.append(chunk)
        remaining -= chunk
    if len(chunks) > 1 and chunks[-1] == 1 and chunks[-2] >= 3:
        chunks[-2] -= 1
        chunks[-1] = 2
    return chunks


def build_plate_matrix(total_units_x, total_units_y, max_units_x, max_units_y):
    plate_matrix = np.zeros((total_units_y, total_units_x), dtype=int)
    plate_counter = 1

    x_splits = compute_splits(total_units_x, max_units_x)
    y_splits = compute_splits(total_units_y, max_units_y)

    y_pos = 0
    for plate_y in y_splits:
        x_pos = 0
        for plate_x in x_splits:
            plate_matrix[y_pos:y_pos + plate_y, x_pos:x_pos + plate_x] = plate_counter
            plate_counter += 1
            x_pos += plate_x
        y_pos += plate_y

    return plate_matrix, plate_counter - 1


def get_plate_centers(layout, grid_size=42):
    centers = {}
    for plate_id in np.unique(layout):
        if plate_id == 0:
            continue
        rows, cols = np.where(layout == plate_id)
        center_x = (cols.min() + cols.max() + 1) / 2 * grid_size
        center_y = (rows.min() + rows.max() + 1) / 2 * grid_size
        centers[int(plate_id)] = (center_x, center_y)
    return centers


# Reduce max_units so that every plate (including its padding) fits in the printer.
# The old approach checked max_units * 42 + leftover, but the rightmost/topmost plate
# is often smaller than max_units — compute_splits gives the actual plate sizes.
def adjust_max_units_for_padding(total_units_x, total_units_y, max_units_x, max_units_y,
                                 leftover_x, leftover_y, printer_x_mm, printer_y_mm, padding_option):
    while True:
        x_splits = compute_splits(total_units_x, max_units_x)
        y_splits = compute_splits(total_units_y, max_units_y)
        if padding_option == "Corner Justify":
            x_ok = x_splits[-1] * 42 + leftover_x <= printer_x_mm
            y_ok = y_splits[-1] * 42 + leftover_y <= printer_y_mm
        else:  # Center Justify: largest plate + half padding on each edge
            x_ok = x_splits[0] * 42 + leftover_x / 2 <= printer_x_mm
            y_ok = y_splits[0] * 42 + leftover_y / 2 <= printer_y_mm
        if x_ok and y_ok:
            return max_units_x, max_units_y
        if not x_ok:
            max_units_x -= 1
        if not y_ok:
            max_units_y -= 1


def determine_padding(plate_matrix, leftover_x, leftover_y, padding_option):
    y, x = plate_matrix.shape
    result = {}

    for plate in [p for p in np.unique(plate_matrix) if p != 0]:
        rows, cols = np.where(plate_matrix == plate)
        min_row, max_row = rows.min(), rows.max()
        min_col, max_col = cols.min(), cols.max()

        plate_x = max_col - min_col + 1
        plate_y = max_row - min_row + 1

        padding_info = []
        fitx, fity = 0, 0
        padding_x, padding_y = 0.0, 0.0
        if padding_option == "Corner Justify":
            if max_col == x - 1 and leftover_x > 0:
                padding_info.append(f"{round(leftover_x, 1)}mm Right")
                fitx = 1
                padding_x = leftover_x
            if max_row == y - 1 and leftover_y > 0:
                padding_info.append(f"{round(leftover_y, 1)}mm Top")
                fity = 1
                padding_y = leftover_y
        elif padding_option == "Center Justify":
            is_leftmost = min_col == 0
            is_rightmost = max_col == x - 1
            is_bottommost = min_row == 0
            is_topmost = max_row == y - 1
            if leftover_x > 0:
                if is_leftmost and is_rightmost:
                    fitx = 0
                    padding_x = leftover_x / 2
                    padding_info.append(f"{round(leftover_x / 2, 1)}mm Left")
                    padding_info.append(f"{round(leftover_x / 2, 1)}mm Right")
                elif is_leftmost:
                    fitx = -1
                    padding_x = leftover_x / 2
                    padding_info.append(f"{round(leftover_x / 2, 1)}mm Left")
                elif is_rightmost:
                    fitx = 1
                    padding_x = leftover_x / 2
                    padding_info.append(f"{round(leftover_x / 2, 1)}mm Right")
            if leftover_y > 0:
                if is_bottommost and is_topmost:
                    fity = 0
                    padding_y = leftover_y / 2
                    padding_info.append(f"{round(leftover_y / 2, 1)}mm Bottom")
                    padding_info.append(f"{round(leftover_y / 2, 1)}mm Top")
                elif is_bottommost:
                    fity = -1
                    padding_y = leftover_y / 2
                    padding_info.append(f"{round(leftover_y / 2, 1)}mm Bottom")
                elif is_topmost:
                    fity = 1
                    padding_y = leftover_y / 2
                    padding_info.append(f"{round(leftover_y / 2, 1)}mm Top")

        label = f"{plate_x}x{plate_y}"
        if padding_info:
            label += f" ({', '.join(padding_info)})"

        result[int(plate)] = {
            'gridx': plate_x,
            'gridy': plate_y,
            'fitx': fitx,
            'fity': fity,
            'padding_x': padding_x,
            'padding_y': padding_y,
            'label': label,
        }

    return result


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
    result = {}
    for plate in [p for p in np.unique(plate_matrix) if p != 0]:
        rows, cols = np.where(plate_matrix == plate)
        plate_x = cols.max() - cols.min() + 1
        plate_y = rows.max() - rows.min() + 1
        result[int(plate)] = (plate_x, plate_y)
    return result


def generate_openscad_code(gridx: int, gridy: int, padding_x: int = 0, padding_y: int = 0, fitx: int = 0,
                           fity: int = 0):
    with open("baseplate.scad.j2", "r") as f:
        scad_template = Template(str(f.read()))

    return scad_template.render(grid_x=gridx,
                                grid_y=gridy,
                                padding_x=padding_x,
                                padding_y=padding_y,
                                fit_x=fitx,
                                fit_y=fity)


def create_zip_from_scad_dict(scads_dict):
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zip_file:
        for key, value in scads_dict.items():
            zip_file.writestr(key, value)

    return zip_buffer.getvalue()


def main():
    st.title("Gridfinity Baseplate Layout Calculator - Optimized to Avoid Any 1x Dimension Baseplates")

    # Dropdowns for units selection
    printer_units = st.selectbox("Select Printer Dimensions Units:", options=UNITS)
    space_units = st.selectbox("Select Area Dimensions Units:", options=UNITS, )

    # Inputs with updated labels
    printer_x = st.number_input(f"Printer Max Build Size X ({printer_units}):",
                                value=227 if printer_units == "Millimeters" else 8.94)
    printer_y = st.number_input(f"Printer Max Build Size Y ({printer_units}):",
                                value=255 if printer_units == "Millimeters" else 10.04)
    space_x = st.number_input(f"Enter the space's X dimension you want to fill ({space_units}):",
                              value=1000 if space_units == "Millimeters" else 39.37)
    space_y = st.number_input(f"Enter the space's Y dimension you want to fill ({space_units}):",
                              value=800 if space_units == "Millimeters" else 31.5)

    # Convert to millimeters if needed
    printer_x_mm = convert_to_mm(printer_x, printer_units)
    printer_y_mm = convert_to_mm(printer_y, printer_units)
    space_x_mm = convert_to_mm(space_x, space_units)
    space_y_mm = convert_to_mm(space_y, space_units)

    # Padding option dropdown
    padding_option = st.selectbox("Select Padding Calculation Option:",
                                  ["Corner Justify", "Center Justify", "No Padding Calculation"])

    if st.button("Calculate Layout"):
        # Get the baseplates based on printer size and desired space dimensions.
        layout, leftover_x, leftover_y, total_units_x, total_units_y, max_units_x, max_units_y = calculate_baseplates(
            printer_x_mm, printer_y_mm, space_x_mm, space_y_mm)

        if padding_option != "No Padding Calculation":
            max_units_x, max_units_y = adjust_max_units_for_padding(
                total_units_x, total_units_y, max_units_x, max_units_y,
                leftover_x, leftover_y, printer_x_mm, printer_y_mm, padding_option)
            layout, _ = build_plate_matrix(total_units_x, total_units_y, max_units_x, max_units_y)

        # Store results in session state
        st.session_state.layout = layout
        st.session_state.leftover_x = leftover_x
        st.session_state.leftover_y = leftover_y
        st.session_state.total_units_x = total_units_x
        st.session_state.total_units_y = total_units_y

        # Display results
        st.write(f"Total fill area Gridfinity units (X x Y): {total_units_x} x {total_units_y}")
        st.write(f"Leftover X distance: {round(leftover_x, 1)} mm")
        st.write(f"Leftover Y distance: {round(leftover_y, 1)} mm")
        max_plate_size = f"{max_units_x}x{max_units_y} Gridfinity units"
        st.write(f"Maximum plate size your printer can handle (including padding): {max_plate_size}")

    if 'layout' in st.session_state:
        layout = st.session_state.layout
        leftover_x = st.session_state.leftover_x
        leftover_y = st.session_state.leftover_y
        total_units_x = st.session_state.total_units_x
        total_units_y = st.session_state.total_units_y

        scad_dict = dict()

        if padding_option != "No Padding Calculation":
            bill_of_materials_with_padding = determine_padding(layout, leftover_x, leftover_y, padding_option)
            st.write("Bill of Materials with Padding:")

            for plate_id, info in bill_of_materials_with_padding.items():
                gridx = info['gridx']
                gridy = info['gridy']
                fitx = info['fitx']
                fity = info['fity']
                padding_x = info['padding_x']
                padding_y = info['padding_y']
                label = info['label']

                st.write(f"Plate {plate_id}: {label}")

                scad_code = generate_openscad_code(gridx, gridy, padding_x, padding_y, fitx, fity)
                filename = f"Plate_{plate_id}_{label.replace(' ', '_')}.scad"
                scad_dict[filename] = scad_code

                buffer = io.BytesIO()
                buffer.write(scad_code.encode())
                buffer.seek(0)

                st.download_button(
                    label=f"Download OpenSCAD Code for Plate {plate_id} ({label})",
                    data=buffer,
                    file_name=filename,
                    mime="text/plain"
                )

            zip_data = create_zip_from_scad_dict(scad_dict)
            st.download_button(
                label="Download all SCADs with padding as ZIP file",
                data=zip_data,
                file_name="allScads.zip",
                mime="application/zip"
            )

        else:
            # Summarize the plates without padding
            bill_of_materials = summarize_bom(layout)
            st.write("Bill of Materials:")

            for plate_id, (gridx, gridy) in bill_of_materials.items():
                st.write(f"Plate {plate_id}: {gridx}x{gridy}")

                scad_code = generate_openscad_code(gridx, gridy)
                filename = f"Plate_{plate_id}_{gridx}x{gridy}.scad"
                scad_dict[filename] = scad_code
                buffer = io.BytesIO()
                buffer.write(scad_code.encode())
                buffer.seek(0)

                st.download_button(
                    label=f"Download OpenSCAD Code for Plate {plate_id} ({gridx}x{gridy})",
                    data=buffer,
                    file_name=filename,
                    mime="text/plain"
                )

            zip_data = create_zip_from_scad_dict(scad_dict)
            st.download_button(
                label="Download all SCADs with no padding as ZIP file",
                data=zip_data,
                file_name="allScads.zip",
                mime="application/zip"
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

        for plate_id, (cx, cy) in get_plate_centers(layout).items():
            ax.text(cx, cy, str(plate_id),
                    ha='center', va='center',
                    fontsize=10, fontweight='bold', color='white',
                    path_effects=[patheffects.withStroke(linewidth=2, foreground='black')],
                    zorder=5)

        ax.set_xlim(-leftover_x / 2 if padding_option == "Center Justify" else 0,
                    total_units_x * 42 + leftover_x / 2 if padding_option == "Center Justify" else total_units_x * 42 + leftover_x)
        ax.set_ylim(-leftover_y / 2 if padding_option == "Center Justify" else 0,
                    total_units_y * 42 + leftover_y / 2 if padding_option == "Center Justify" else total_units_y * 42 + leftover_y)
        ax.set_aspect('equal', adjustable='box')

        st.pyplot(fig)


if __name__ == "__main__":
    main()
