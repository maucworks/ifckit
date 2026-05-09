import bpy
import ifcopenshell
from ifcopenshell import geom
import numpy as np
import os

# Path to IFC file
ifc_path = os.path.expanduser("~/L140-py-ifckit/output/test_spatial_structure.ifc")

# Load IFC
model = ifcopenshell.open(ifc_path)
settings = geom.settings()

# Clear scene
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# Import each product
for product in model.by_type('IfcProduct'):
    if not (hasattr(product, 'Representation') and product.Representation):
        continue
    
    try:
        shape = geom.create_shape(settings, product)
        verts = np.array(shape.geometry.verts).reshape(-1, 3)
        faces = np.array(shape.geometry.faces).reshape(-1, 3)
        
        # Create mesh
        mesh = bpy.data.meshes.new(name=product.Name or product.is_a())
        mesh.from_pydata(verts.tolist(), [], faces.tolist())
        mesh.update()
        
        # Create object
        obj = bpy.data.objects.new(product.Name or product.is_a(), mesh)
        bpy.context.collection.objects.link(obj)
        
        print(f"Imported: {product.is_a()} '{product.Name}' - {len(verts)} verts, {len(faces)} faces")
        
    except Exception as e:
        print(f"Error importing {product.is_a()} '{product.Name}': {e}")

print("Done!")
