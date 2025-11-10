import pandas as pd
from shapely.geometry import Point, Polygon
import xml.etree.ElementTree as ET
from pyproj import Transformer


def parse_kml_polygons(kml_file_path):
    ns = {'kml': 'http://www.opengis.net/kml/2.2'}
    tree = ET.parse(kml_file_path)
    root = tree.getroot()

    placemarks = root.findall('.//kml:Placemark', ns)
    polygons_data = []

    for placemark in placemarks:
        data = {}

        # Extract metadata
        ext_data = placemark.find('.//kml:ExtendedData/kml:SchemaData', ns)
        if ext_data is not None:
            for sd in ext_data.findall('kml:SimpleData', ns):
                name = sd.attrib.get('name')
                value = sd.text
                data[name] = value

        # Extract polygon coordinates
        coords_text = placemark.find('.//kml:coordinates', ns)
        if coords_text is not None:
            coords_raw = coords_text.text.strip().split()
            coords = [(float(c.split(',')[0]), float(c.split(',')[1])) for c in coords_raw]
            if coords[0] != coords[-1]:
                coords.append(coords[0])
            polygon = Polygon(coords)
            data['geometry'] = polygon
            polygons_data.append(data)

    return polygons_data


def assign_wards_to_schools(schools_df, wards_data):
    schools_df = schools_df.dropna(subset=["latitude_coordinate", "longitude_coordinate"])
    schools_df["latitude_coordinate"] = pd.to_numeric(schools_df["latitude_coordinate"], errors='coerce')
    schools_df["longitude_coordinate"] = pd.to_numeric(schools_df["longitude_coordinate"], errors='coerce')
    schools_df = schools_df.dropna(subset=["latitude_coordinate", "longitude_coordinate"])

    # Initialize new columns
    schools_df["WNo_SEC"] = None
    schools_df["AC_No"] = None
    schools_df["AC_No_1"] = None
    schools_df["AC_Name"] = None
    schools_df["Ward_No"] = None
    schools_df["WardName"] = None
    schools_df["BORDER_FLAG"] = False

    transformer = Transformer.from_crs("EPSG:4326", "EPSG:32643", always_xy=True)

    for idx, school in schools_df.iterrows():
        lon, lat = school["longitude_coordinate"], school["latitude_coordinate"]
        point = Point(lon, lat)

        x, y = transformer.transform(lon, lat)
        projected_point = Point(x, y)

        for ward in wards_data:
            polygon = ward.get('geometry')
            if not polygon:
                continue

            if polygon.contains(point):
                projected_coords = [transformer.transform(*coord) for coord in polygon.exterior.coords]
                projected_polygon = Polygon(projected_coords)

                distance_to_boundary = projected_polygon.boundary.distance(projected_point)

                schools_df.at[idx, "WNo_SEC"] = ward.get("WNo_SEC")
                schools_df.at[idx, "AC_No"] = ward.get("AC_No")
                schools_df.at[idx, "AC_No_1"] = ward.get("AC_No_1")
                schools_df.at[idx, "AC_Name"] = ward.get("AC_Name")
                schools_df.at[idx, "Ward_No"] = ward.get("Ward_No")
                schools_df.at[idx, "WardName"] = ward.get("WardName")
                schools_df.at[idx, "BORDER_FLAG"] = distance_to_boundary <= 10
                break

    return schools_df


def main():
    schools_df = pd.read_csv("input.csv")
    wards_data = parse_kml_polygons("delhi_wards.kml")
    updated_schools_df = assign_wards_to_schools(schools_df, wards_data)

    # ✅ Select only the required columns
    output_columns = [
        "phone_number", "WNo_SEC", "AC_No", "AC_No_1",
        "AC_Name", "Ward_No", "WardName", "BORDER_FLAG"
    ]

    # Check all required columns exist
    missing_cols = [col for col in output_columns if col not in updated_schools_df.columns]
    if missing_cols:
        raise Exception(f"Missing columns in DataFrame: {missing_cols}")

    updated_schools_df[output_columns].to_csv("output.csv", index=False)
    print("✅ Done! File saved as 'output.csv'")


if __name__ == "__main__":
    main()
