# Problem 2 – Rectagular plate with a hole
In this problem we will try to understand the role of mesh refinement in getting accurate results. 


We will use the following geometry.
![Geometry](Pictures_P2/Geometry.png)
## Follow the following instructions.

Open ANSYS Workbench (I used 2023R2). There might be some variations in where the software options are depending on version.

![Locate External Model](Pictures_P2/1.png)

Drag and drop `Static Structural` model inside the project schematic.

![Locate External Model](Pictures_P2/2.png)

Right click on Geometry and choose `New SpaceClaim Geometry`. There are other options to create geometry: choose any. We will follow `New SpaceClaim Geometry`.

![Locate External Model](Pictures_P2/3.png)

Follow the steps below to create the geometry. I used `Constraints` to center the circle inside the rectangle.

![Locate External Model](Pictures_P2/4.png)

![Locate External Model](Pictures_P2/5.png)

![Locate External Model](Pictures_P2/6.png)

![Locate External Model](Pictures_P2/7.png)

![Locate External Model](Pictures_P2/8.png)

![Locate External Model](Pictures_P2/9.png)

![Locate External Model](Pictures_P2/10.png)

![Locate External Model](Pictures_P2/11.png)

![Locate External Model](Pictures_P2/12.png)

Once you have finshed creating geometry. Minimize the window and get back to `Workbench`. Open `Model`. You should see the geometry. 

![Locate External Model](Pictures_P2/14.png)

Don't forget to choose the units in mm ..

![Locate External Model](Pictures_P2/22.png)

Right click on `Mesh` and `>Insert>Method`

![Locate External Model](Pictures_P2/16.png)

Select the geometry (whole body not a face) and click on apply.

![Locate External Model](Pictures_P2/17.png)

![Locate External Model](Pictures_P2/18.png)

Choose the `Cartesian` method.

![Locate External Model](Pictures_P2/19.png)

Right click on `Mesh` and generate the mesh.

![Generate Mesh](Pictures_P2/15.png)


![Locate External Model](Pictures_P2/20.png)

![Locate External Model](Pictures_P2/21.png)

![Locate External Model](Pictures_P2/22.png)
