## About in2cs2

- Based on **ucupaint** Blender addon
   - years of development and artists usage and feedback
   - free alternative to Substance Painter and/or Photoshop (although still useful next to it)
- Works on **any Blender version** (2.7 until 5.1)
- Bake textures **directly to CS2 render pipeline** without leaving Blender  
   - no need to swizzle channels in Photoshop, superPNG!
   - work from Blender directly into Cities Skylines 2 editor

> *About ucupaint*
> - Ucupaint Download/Repo : [https://github.com/ucupumar/ucupaint](https://github.com/ucupumar/ucupaint "https://github.com/ucupumar/ucupaint")
> - Ucupaint Wiki/Documentation : [https://ucupumar.github.io/ucupaint-wiki/](https://ucupumar.github.io/ucupaint-wiki/ "https://ucupumar.github.io/ucupaint-wiki/")

### Who is in2cs2 for

Cities Skylines II asset creators from beginner to expert.

- Improve your creation workflow
- Bake with confidence thanks to the ucupaint underlying system
- Save time on redundant operations and verifications

### CitiesSkylines2 specific features

*Modelling*  
- **Scene units and scale** validation (avoid missed exports)
   - warns user if scene unit is not Metric
   - warns user if unit scale is not 1:1
- **Naming convention** with function to Fix names
   - matches material and object name
   - matches mesh and object name
   - supports all possible LOD types and submesh prefixes
- **Smart FBX export** function (file named after the object)
   - supports modifiers (non-destructive export)
   - supports non-zeroed location (applies only Rotation and Scale)
      - allows side-by-side asset placement in the scene
      - prevents missed exports with bad scaling or Z-up imported meshes

*Texturing*  
- Bakes to any supported sizes (512, 1024, 2048 or 4096)  
- CS2-compliant texture maps
   - auto-binding to Principled BSDF shader
- One-click **Save CS2 textures**,
   - no need to rename or convert files
   - import-ready, each and every time!
