from itertools import product
from logging import root
from multiprocessing import parent_process
import adsk.core, adsk.fusion, adsk.cam, traceback
from math import radians, pi, cos, degrees

# Global design parameters
defaultHoles = 6            # number of screw holes
defaultRH = 3               # screw hole radius
defaultLength = 100
defaultTheta = radians(70) # [deg] angle between sensor-pipe and main-pipe
defaultD = 40              # [cm] pipe/valve diameter

# Global set of event _handlers to keep them referenced for the duration of the command
_handlers = []

app = adsk.core.Application.get()
if app:
    ui = app.userInterface

new_comp = None

def createNewComponent():
    # Get the active design.
    product = app.activeProduct
    design = adsk.fusion.Design.cast(product)
    root_comp = design.rootComponent
    all_occs = root_comp.occurrences
    new_occ = all_occs.addNewComponent(adsk.core.Matrix3D.create())
    return new_occ.component


class FlowValveCommandExecuteHandler(adsk.core.CommandEventHandler):
    """Event handler that reacts to any changes the user makes to any of the command inputs."""
    def __init__(self):
        super().__init__()
    def notify(self, args: adsk.core.CommandEventArgs):
        try:
            unitsMgr = app.activeProduct.unitsManager
            command: adsk.core.Command = args.firingEvent.sender
            inputs = command.commandInputs

            flow_valve = FlowValve()
            for input in inputs:
                if input.id == 'theta':
                    flow_valve.theta = unitsMgr.evaluateExpression(input.expression, "deg")
                elif input.id == 'D':
                    flow_valve.D = unitsMgr.evaluateExpression(input.expression, "cm")
                elif input.id == 'L':
                    flow_valve.L = unitsMgr.evaluateExpression(input.expression, "cm")
                elif input.id == 'RH':
                    flow_valve.RH = unitsMgr.evaluateExpression(input.expression, "cm")
                elif input.id == 'H':
                    flow_valve.H = unitsMgr.evaluateExpression(input.expression, "pcs")
                elif input.id == 'P':
                    input.formattedText = f'~ {round(flow_valve.P, 2)} cm'
                elif input.id == 'WT':
                    input.formattedText = f'~ {round(flow_valve.WT, 2)} cm'
            flow_valve.create_flow_valve()
            args.isValidResult = True

        except:
            if ui:
                ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))


class FlowValveCommandDestroyHandler(adsk.core.CommandEventHandler):
    """Event handler that reacts to when the command is destroyed. This terminates the script."""
    def __init__(self):
        super().__init__()
    def notify(self, args: adsk.core.CommandEventArgs):
        try:
            # when the command is done, terminate the script
            # this will release all globals which will remove all event _handlers
            adsk.terminate()
        except:
            if ui:
                ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))


class FlowValveCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    """
    Event handler that reacts when the command definition is executed which
    results in the command being created and this event being fired.
    """  
    def __init__(self):
        super().__init__()        
    def notify(self, args: adsk.core.CommandEventArgs):
        try:
            # Get the command that was created.
            cmd = adsk.core.Command.cast(args.command)

            # Connect to the command event handler.
            onExecute = FlowValveCommandExecuteHandler()
            cmd.execute.add(onExecute)
            _handlers.append(onExecute) # keep the handler referenced beyond this function

            # Connect to the command event handler.
            onExecutePreview = FlowValveCommandExecuteHandler()
            cmd.executePreview.add(onExecutePreview)
            _handlers.append(onExecutePreview) # keep the handler referenced beyond this function

            # Connect to the command destroyed event.
            onDestroy = FlowValveCommandDestroyHandler()
            cmd.destroy.add(onDestroy)
            _handlers.append(onDestroy) # keep the handler referenced beyond this function

            # Get the CommandInputs collection associated with the command.
            inputs = cmd.commandInputs

            # Define the command dialog image/illustration
            #_imgInput = inputs.addImageCommandInput('FlowValve', 'Flow valve', 'resources/flow_valve.png')
            #_imgInput.isFullWidth = True

            # Define the value inputs for the command
            _initTheta = adsk.core.ValueInput.createByReal(defaultTheta)
            inputs.addValueInput('theta', 'Angle (θ)', 'deg', _initTheta)

            _initD = adsk.core.ValueInput.createByReal(defaultD)
            inputs.addValueInput('D', 'Main Pipe Outer Diameter (D)', 'cm', _initD)
           
            _initL = adsk.core.ValueInput.createByReal(defaultLength)
            inputs.addValueInput('L', 'Length (L)', 'cm', _initL)

            _initRH = adsk.core.ValueInput.createByReal(defaultRH)
            inputs.addValueInput('RH', 'Screw hole radius', 'cm', _initRH)

            _initH = adsk.core.ValueInput.createByReal(defaultHoles)
            inputs.addValueInput('H', 'Number of screw holes', 'pcs', _initH)

           
            # Define a read-only textbox for the command
            _initP = round(defaultD/cos(pi/2-defaultTheta), 2)
            inputs.addTextBoxCommandInput('P', 'Transducer distance (P)', f'~ {_initP} cm', 1, True)
            _initWT = round(defaultD/2-(defaultD/2-defaultD/10))
            inputs.addTextBoxCommandInput('WT', 'Wall thickness (WT)', f'~ {_initWT} cm', 1, True)
        except:
            if ui:
                ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))


class FlowValve():
    def __init__(self):
        # Design parameters
        self._H = defaultHoles               # number of holes for bolts
        self._RH = defaultRH                 # radius for botls
        self._theta = defaultTheta           # angle between sensor-pipe and main-pipe
        self._D = defaultD                   # main pipe diameter
        self._L = defaultLength
        self._WT = self.calculate_WT()       # wall thickness of main pipe
        self._d = 15                         # sensor pipe diameter
        # self._P = defaultP                 # distance between transducers
        self._P = self.calculate_P()         # distance between transducers

    # Properties
    @property
    def H(self) -> float:
        return self._H
    @H.setter
    def H(self, value: float):
        self._H = value
    @property
    def RH(self) -> float:
        return self._RH
    @RH.setter
    def RH(self, value: float):
        self._RH = value
    @property
    def L(self) -> float:
        return self._L
    @L.setter
    def L(self, value: float):
        self._L = value
    @property
    def theta(self) -> float:
        """Angle between sensor-pipe and main-pipe."""
        return self._theta
    @theta.setter
    def theta(self, value: float):
        """Angle between sensor-pipe and main-pipe."""
        self._theta = value
        self.calculate_P()
    @property
    def D(self) -> float:
        """Main-pipe diameter."""
        return self._D
    @D.setter
    def D(self, value: float):
        """Main-pipe diameter."""
        self._D = value
        self.calculate_P()
    @property
    def P(self) -> float:
        """Distance between transducers."""
        return self._P

    @property
    def WT(self) -> float:
        """Wall thickness of main-pipe"""
        return self._WT

    # Methods
    def calculate_P(self):
        self._P = self._D/cos(pi/2-self._theta)
        return self._P

    def calculate_WT(self):
        self._WT = self._D/2-(self.D/2-self.D/10)
        return self._WT

    def create_flow_valve(self):
        """Creates and builds the flow valve based on specified property values"""

        new_comp = createNewComponent()
        if new_comp is None:
            ui.messageBox('New component failed to create', 'New Component Failed')
            return

        new_comp.name = f'Flow-valve (D{self.D}cm θ{degrees(self.theta)}deg)'
        # Defining a global center point
        center_global = new_comp.originConstructionPoint.geometry
       

        # SENSOR PIPE ------------------------------------------------------------------
        """This part creates the sensor pipe for the flow meter. It is created on an angled plane."""
        "Construction Plane"
        const_plane_sp_input = new_comp.constructionPlanes.createInput()
        const_plane_sp_input.setByAngle(linearEntity=new_comp.xConstructionAxis, angle=adsk.core.ValueInput.createByReal(self.theta), planarEntity=new_comp.xYConstructionPlane)
        const_plane_sp = new_comp.constructionPlanes.add(const_plane_sp_input)
        "Sketch"
        sketch_sp = new_comp.sketches.add(const_plane_sp)
        center_sp = sketch_sp.modelToSketchSpace(center_global)
        circles_sp = sketch_sp.sketchCurves.sketchCircles
        circle_sp_o = circles_sp.addByCenterRadius(centerPoint=center_sp, radius=self._d/2)
        circle_sp_i = circles_sp.addByCenterRadius(centerPoint=circle_sp_o.centerSketchPoint, radius=self._d/2-self._d/10)
        "Extrude"
        pipe_sp_profile = sketch_sp.profiles.item(0)  # get the pipe profile (profile between inner and outer circle)
        ext_pipe_sp_input = new_comp.features.extrudeFeatures.createInput(profile=pipe_sp_profile, operation=adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        ext_pipe_sp_input.setDistanceExtent(isSymmetric=True, distance=adsk.core.ValueInput.createByReal(self.P/2+70))
        bodyOne = new_comp.features.extrudeFeatures.add(ext_pipe_sp_input)

        # SENSOR PIPE SPOOL PIECE ------------------------------------------------------------------
        """This part creates the spool pieces of the sensor pipe. It is extended as 
        new bodies at the ends of the pipe."""
        #Body
        body = bodyOne.bodies.item(0)
        circularFace = None
        for face in body.faces:
            geom = face.geometry
            if geom.surfaceType == adsk.core.SurfaceTypes.CylinderSurfaceType:
                circularFace = face
                break
        "Top spool piece"
        #onstruction Axis
        const_axis_sp_input = new_comp.constructionAxes.createInput()
        const_axis_sp_input.setByCircularFace(circularFace)
        const_axis_sp = new_comp.constructionAxes.add(const_axis_sp_input)
        #Construction Offset Plane
        const_offsetPlane_input = new_comp.constructionPlanes.createInput()
        const_offsetPlane_input.setByOffset(planarEntity=pipe_sp_profile, offset=adsk.core.ValueInput.createByReal(self.P/2+70))
        const_offsetPlane = new_comp.constructionPlanes.add(const_offsetPlane_input)
        #Centerpoint
        center_sp = adsk.core.Point3D.create(0, 0, 0)
        #Sketch
        sketch_SP = new_comp.sketches.add(const_offsetPlane)
        circle_SP = sketch_SP.sketchCurves.sketchCircles
        circle_SP_o = circle_SP.addByCenterRadius(centerPoint=center_sp, radius=self._d-self._d/10)
        circle_SP_i = circle_SP.addByCenterRadius(centerPoint=center_sp, radius=self._d/2-self._d/10)
        #Extrude
        pipe_SP_profile = sketch_SP.profiles.item(0)
        ext_pipe_SP_input = new_comp.features.extrudeFeatures.createInput(profile=pipe_SP_profile, operation=adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        ext_pipe_SP_input.setDistanceExtent(isSymmetric=True, distance=adsk.core.ValueInput.createByReal(1))
        bodyTwo = new_comp.features.extrudeFeatures.add(ext_pipe_SP_input)
        #Sketch
        parent_sketch = sketch_SP.sketchCurves.sketchCircles.addByCenterRadius(centerPoint=adsk.core.Point3D.create(0,self._d-5,0), radius=2)                  #item(2)
        #Extrude Cut
        spool_profile = sketch_SP.profiles.item(2)
        ext_spool_hole = new_comp.features.extrudeFeatures.createInput(profile=spool_profile, operation=adsk.fusion.FeatureOperations.CutFeatureOperation)
        ext_spool_hole.setDistanceExtent(isSymmetric=True, distance=adsk.core.ValueInput.createByReal(0.2*self._d))
        circle_cut = new_comp.features.extrudeFeatures.add(ext_spool_hole)
        #Circular pattern
        CircularPatterns = new_comp.features.circularPatternFeatures
        inputEntitiesCollection = adsk.core.ObjectCollection.create()
        inputEntitiesCollection.add(circle_cut)
        inputAxis = const_axis_sp
        CircularPatternInput = CircularPatterns.createInput(inputEntitiesCollection, inputAxis)
        CircularPatternInput.quantity = adsk.core.ValueInput.createByReal(self.H)
        CircularPatternInput.totalAngle = adsk.core.ValueInput.createByString('360 deg')
        CircularPatternInput.isSymmetric = False
        CircularPattern = CircularPatterns.add(CircularPatternInput)
        "Bottom spool piece"
        #Construction axis
        const_axis_sp_input = new_comp.constructionAxes.createInput()
        const_axis_sp_input.setByCircularFace(circularFace)
        const_axis_sp = new_comp.constructionAxes.add(const_axis_sp_input)
        #Cosntruction Offset Plane
        const_offsetPlane_input = new_comp.constructionPlanes.createInput()
        const_offsetPlane_input.setByOffset(planarEntity=pipe_sp_profile, offset=adsk.core.ValueInput.createByReal(-self.P/2-70))
        const_offsetPlane = new_comp.constructionPlanes.add(const_offsetPlane_input)
        #Center Point
        center_sp = adsk.core.Point3D.create(0, 0, 0)
        #Sketch
        sketch_SP = new_comp.sketches.add(const_offsetPlane)
        circle_SP = sketch_SP.sketchCurves.sketchCircles
        circle_SP_o = circle_SP.addByCenterRadius(centerPoint=center_sp, radius=self._d-self._d/10)
        circle_SP_i = circle_SP.addByCenterRadius(centerPoint=center_sp, radius=self._d/2-self._d/10)
        #Extrude
        pipe_SP_profile = sketch_SP.profiles.item(0)
        ext_pipe_SP_input = new_comp.features.extrudeFeatures.createInput(profile=pipe_SP_profile, operation=adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        ext_pipe_SP_input.setDistanceExtent(isSymmetric=True, distance=adsk.core.ValueInput.createByReal(1))
        bodyTwo = new_comp.features.extrudeFeatures.add(ext_pipe_SP_input)
        #Sketch
        parent_sketch = sketch_SP.sketchCurves.sketchCircles.addByCenterRadius(centerPoint=adsk.core.Point3D.create(0,self._d-5,0), radius=2)                 
        #Extrude Cut
        spool_profile = sketch_SP.profiles.item(2)
        ext_spool_hole = new_comp.features.extrudeFeatures.createInput(profile=spool_profile, operation=adsk.fusion.FeatureOperations.CutFeatureOperation)
        ext_spool_hole.setDistanceExtent(isSymmetric=True, distance=adsk.core.ValueInput.createByReal(0.2*self._d))
        circle_cut = new_comp.features.extrudeFeatures.add(ext_spool_hole)
        #Circular Pattern
        CircularPatterns = new_comp.features.circularPatternFeatures
        inputEntitiesCollection = adsk.core.ObjectCollection.create()
        inputEntitiesCollection.add(circle_cut)
        inputAxis = const_axis_sp
        CircularPatternInput = CircularPatterns.createInput(inputEntitiesCollection, inputAxis)
        CircularPatternInput.quantity = adsk.core.ValueInput.createByReal(self.H)
        CircularPatternInput.totalAngle = adsk.core.ValueInput.createByString('360 deg')
        CircularPatternInput.isSymmetric = False
        CircularPattern = CircularPatterns.add(CircularPatternInput)
        
        # MAIN PIPE --------------------------------------------------------------------
        """This part creates the main pipe of the flow meter which is on the xy plane."""
        #Sketch
        sketch_mp = new_comp.sketches.add(new_comp.xYConstructionPlane)
        center_mp = sketch_mp.modelToSketchSpace(center_global)
        circles_mp = sketch_mp.sketchCurves.sketchCircles
        circle_mp_o = circles_mp.addByCenterRadius(centerPoint=center_mp, radius=self.D/2)
        circle_mp_i = circles_mp.addByCenterRadius(centerPoint=circle_mp_o.centerSketchPoint, radius=self.D/2-self.D/10)
        #Extrude
        profiles_mp = adsk.core.ObjectCollection.create()
        [profiles_mp.add(profile) for profile in sketch_mp.profiles]
        ext_pipe_mp_cut_input = new_comp.features.extrudeFeatures.createInput(profile=profiles_mp, operation=adsk.fusion.FeatureOperations.CutFeatureOperation)
        ext_pipe_mp_cut_input.setDistanceExtent(isSymmetric=True, distance=adsk.core.ValueInput.createByReal(self.L/2))
        new_comp.features.extrudeFeatures.add(ext_pipe_mp_cut_input)
        #Join (main pipe and sensor pipe)
        pipe_mp_profile = sketch_mp.profiles.item(0)  # get the pipe profile (profile between inner and outer circle)
        ext_pipe_mp_join_input = new_comp.features.extrudeFeatures.createInput(profile=pipe_mp_profile, operation=adsk.fusion.FeatureOperations.JoinFeatureOperation)
        ext_pipe_mp_join_input.setDistanceExtent(isSymmetric=True, distance=adsk.core.ValueInput.createByReal(self.L/2))
        new_comp.features.extrudeFeatures.add(ext_pipe_mp_join_input)
        #Extrude Cut
        pipe_sp_profile_i = sketch_sp.profiles.item(1)  # get the center profile (profile by inner circle)
        ext_pipe_sp_i_input = new_comp.features.extrudeFeatures.createInput(profile=pipe_sp_profile_i, operation=adsk.fusion.FeatureOperations.CutFeatureOperation)
        ext_pipe_sp_i_input.setDistanceExtent(isSymmetric=True, distance=adsk.core.ValueInput.createByReal(self.P/2 + 70*3))
        new_comp.features.extrudeFeatures.add(ext_pipe_sp_i_input)
        "Spool piece right"
        #Construction Offset Plane
        const_offsetPlane_input = new_comp.constructionPlanes.createInput()
        const_offsetPlane_input.setByOffset(planarEntity=new_comp.xYConstructionPlane, offset=adsk.core.ValueInput.createByReal(self.L/2))
        const_offsetPlane = new_comp.constructionPlanes.add(const_offsetPlane_input)
        #Sketch
        sketch_spool = new_comp.sketches.add(const_offsetPlane)
        center_spool = sketch_spool.modelToSketchSpace(adsk.core.Point3D.create(0,0,self.L/2))
        circle_spool = sketch_spool.sketchCurves.sketchCircles
        circle_spool_o = circle_spool.addByCenterRadius(centerPoint=center_spool, radius=self.D)                                                                    #item(0)
        circle_spool_i = circle_spool.addByCenterRadius(centerPoint=circle_spool_o.centerSketchPoint, radius=self.D/2-self.D/10)                                    #item(1)
        #Extrude
        spool_profile = sketch_spool.profiles.item(0)
        ext_spool_input = new_comp.features.extrudeFeatures.createInput(profile=spool_profile, operation=adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        ext_spool_input.setDistanceExtent(isSymmetric=False, distance=adsk.core.ValueInput.createByReal(0.2*self.D))
        new_comp.features.extrudeFeatures.add(ext_spool_input)
        #Sketch
        parent_sketch = sketch_spool.sketchCurves.sketchCircles.addByCenterRadius(centerPoint=adsk.core.Point3D.create(0,self.D-self.D/5,0), radius=self.RH)                  #item(2)
        #Extrude Cut
        spool_profile = sketch_spool.profiles.item(2)
        ext_spool_hole = new_comp.features.extrudeFeatures.createInput(profile=spool_profile, operation=adsk.fusion.FeatureOperations.CutFeatureOperation)
        ext_spool_hole.setDistanceExtent(isSymmetric=True, distance=adsk.core.ValueInput.createByReal(0.2*self.D))
        circle_cut = new_comp.features.extrudeFeatures.add(ext_spool_hole)
        app = adsk.core.Application.get()
        ui = app.userInterface
        design = app.activeProduct
        #Circular Pattern
        CircularPatterns = new_comp.features.circularPatternFeatures
        inputEntitiesCollection = adsk.core.ObjectCollection.create()
        inputEntitiesCollection.add(circle_cut)    
        inputAxis = new_comp.zConstructionAxis
        CircularPatternInput = CircularPatterns.createInput(inputEntitiesCollection, inputAxis)
        CircularPatternInput.quantity = adsk.core.ValueInput.createByReal(self.H)
        CircularPatternInput.totalAngle = adsk.core.ValueInput.createByString('360 deg')
        CircularPatternInput.isSymmetric = False
        CircularPattern = CircularPatterns.add(CircularPatternInput)
        "Spool piece left"
        #Construction offset Plane
        const_offsetPlane_input = new_comp.constructionPlanes.createInput()
        const_offsetPlane_input.setByOffset(planarEntity=new_comp.xYConstructionPlane, offset=adsk.core.ValueInput.createByReal(self.L/2))
        const_offsetPlane = new_comp.constructionPlanes.add(const_offsetPlane_input)
        #Sketch
        sketch_spool = new_comp.sketches.add(const_offsetPlane)
        center_spool = sketch_spool.modelToSketchSpace(adsk.core.Point3D.create(0,0,-self.L/2))
        circle_spool = sketch_spool.sketchCurves.sketchCircles
        circle_spool_o = circle_spool.addByCenterRadius(centerPoint=center_spool, radius=self.D)                                                                    #item(0)
        circle_spool_i = circle_spool.addByCenterRadius(centerPoint=circle_spool_o.centerSketchPoint, radius=self.D/2-self.D/10)                                    #item(1)  
        #Extrude
        spool_profile = sketch_spool.profiles.item(0)
        ext_spool_input = new_comp.features.extrudeFeatures.createInput(profile=spool_profile, operation=adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        ext_spool_input.setDistanceExtent(isSymmetric=False, distance=adsk.core.ValueInput.createByReal(-0.2*self.D))
        new_comp.features.extrudeFeatures.add(ext_spool_input)
        #Sketch
        parent_sketch_2 = sketch_spool.sketchCurves.sketchCircles.addByCenterRadius(centerPoint=adsk.core.Point3D.create(0,self.D-self.D/5,-self.L), radius=self.RH)                  #item(2)
        #Extrude Cut
        spool_profile = sketch_spool.profiles.item(2)
        ext_spool_hole = new_comp.features.extrudeFeatures.createInput(profile=spool_profile, operation=adsk.fusion.FeatureOperations.CutFeatureOperation)
        ext_spool_hole.setDistanceExtent(isSymmetric=True, distance=adsk.core.ValueInput.createByReal(0.2*self.D))
        circle_cut = new_comp.features.extrudeFeatures.add(ext_spool_hole)
        app = adsk.core.Application.get()
        ui = app.userInterface
        design = app.activeProduct
        #Circular Pattern
        CircularPatterns = new_comp.features.circularPatternFeatures
        inputEntitiesCollection = adsk.core.ObjectCollection.create()
        inputEntitiesCollection.add(circle_cut)
        inputAxis = new_comp.zConstructionAxis
        CircularPatternInput = CircularPatterns.createInput(inputEntitiesCollection, inputAxis)
        CircularPatternInput.quantity = adsk.core.ValueInput.createByReal(self.H)
        CircularPatternInput.totalAngle = adsk.core.ValueInput.createByString('360 deg')
        CircularPatternInput.isSymmetric = False
        CircularPattern = CircularPatterns.add(CircularPatternInput)

        # BALL VALVE ------------------------------------------------------------------------------------------
        """This part creates a simple constructed ball valve. It consists of five parts: 
        Bottom and Top spool piece, pipe, ball and handle."""
        "Bottom spool piece"
        #Construction Offset Plane
        const_offsetPlane_input = new_comp.constructionPlanes.createInput()
        const_offsetPlane_input.setByOffset(planarEntity=pipe_sp_profile, offset=adsk.core.ValueInput.createByReal(self.P/2+71))
        const_offsetPlane = new_comp.constructionPlanes.add(const_offsetPlane_input)
        center_sp = adsk.core.Point3D.create(0, 0, 0)
        #Sketch
        sketch_SP = new_comp.sketches.add(const_offsetPlane)
        circle_SP = sketch_SP.sketchCurves.sketchCircles
        circle_SP_o = circle_SP.addByCenterRadius(centerPoint=center_sp, radius=self._d-self._d/10)
        circle_SP_i = circle_SP.addByCenterRadius(centerPoint=center_sp, radius=self._d/2-self._d/10)
        #Extrude
        pipe_SP_profile = sketch_SP.profiles.item(0)
        ext_pipe_SP_input = new_comp.features.extrudeFeatures.createInput(profile=pipe_SP_profile, operation=adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        ext_pipe_SP_input.setDistanceExtent(isSymmetric=False, distance=adsk.core.ValueInput.createByReal(2))                                                                             #Endret til 'False' og '2'
        bodyTwo = new_comp.features.extrudeFeatures.add(ext_pipe_SP_input)
        #Sketch
        parent_sketch = sketch_SP.sketchCurves.sketchCircles.addByCenterRadius(centerPoint=adsk.core.Point3D.create(0,self._d-5,0), radius=2)                  #item(2)
        #Extrude Cut
        spool_profile = sketch_SP.profiles.item(2)
        ext_spool_hole = new_comp.features.extrudeFeatures.createInput(profile=spool_profile, operation=adsk.fusion.FeatureOperations.CutFeatureOperation)
        ext_spool_hole.setDistanceExtent(isSymmetric=False, distance=adsk.core.ValueInput.createByReal(0.2*self._d))                                                                      #Endret til 'False'
        circle_cut = new_comp.features.extrudeFeatures.add(ext_spool_hole)
        #Circular Pattern
        CircularPatterns = new_comp.features.circularPatternFeatures
        inputEntitiesCollection = adsk.core.ObjectCollection.create()
        inputEntitiesCollection.add(circle_cut)
        inputAxis = const_axis_sp
        CircularPatternInput = CircularPatterns.createInput(inputEntitiesCollection, inputAxis)
        CircularPatternInput.quantity = adsk.core.ValueInput.createByReal(self.H)
        CircularPatternInput.totalAngle = adsk.core.ValueInput.createByString('360 deg')
        CircularPatternInput.isSymmetric = False
        CircularPattern = CircularPatterns.add(CircularPatternInput)
        "Pipe"
        #Construction Offset Plane
        const_offsetPlane_input = new_comp.constructionPlanes.createInput()
        const_offsetPlane_input.setByOffset(planarEntity=pipe_sp_profile, offset=adsk.core.ValueInput.createByReal(self.P/2+72))
        const_offsetPlane = new_comp.constructionPlanes.add(const_offsetPlane_input)
        #Center Point
        center_sp = adsk.core.Point3D.create(0, 0, 0)
        #Sketch
        sketch_SP = new_comp.sketches.add(const_offsetPlane)
        circle_SP = sketch_SP.sketchCurves.sketchCircles
        circle_SP_o = circle_SP.addByCenterRadius(centerPoint=center_sp, radius=self._d/2)
        circle_SP_i = circle_SP.addByCenterRadius(centerPoint=center_sp, radius=self._d/2-self._d/10)
        #Extrude
        pipe_SP_profile = sketch_SP.profiles.item(0)
        ext_pipe_SP_input = new_comp.features.extrudeFeatures.createInput(profile=pipe_SP_profile, operation=adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        ext_pipe_SP_input.setDistanceExtent(isSymmetric=False, distance=adsk.core.ValueInput.createByReal(30))                                                                           #Endret til 'False'
        bodyBallValvePipe = new_comp.features.extrudeFeatures.add(ext_pipe_SP_input)
        "Pipe box"
        #Construction Offset Plane
        const_offsetPlane_input = new_comp.constructionPlanes.createInput()
        const_offsetPlane_input.setByOffset(planarEntity=pipe_sp_profile, offset=adsk.core.ValueInput.createByReal(self.P/2+87))
        const_offsetPlane = new_comp.constructionPlanes.add(const_offsetPlane_input)
        #Center Point
        center_sp = adsk.core.Point3D.create(0, 0, 0)
        #Sketch
        sketch_SP = new_comp.sketches.add(const_offsetPlane)
        circle_SP = sketch_SP.sketchCurves.sketchCircles
        circle_SP_i = circle_SP.addByCenterRadius(centerPoint=center_sp, radius=self._d/2)
        circle_SP_o = circle_SP.addByCenterRadius(centerPoint=center_sp, radius=self._d/2+6)
        #Extrude
        pipe_SP_profile = sketch_SP.profiles.item(1)
        ext_pipe_SP_input = new_comp.features.extrudeFeatures.createInput(profile=pipe_SP_profile, operation=adsk.fusion.FeatureOperations.JoinFeatureOperation)
        ext_pipe_SP_input.setDistanceExtent(isSymmetric=True, distance=adsk.core.ValueInput.createByReal(7.5))                                                                           #Endret til 'False'
        boxBallValvePipe = new_comp.features.extrudeFeatures.add(ext_pipe_SP_input)
        
        #Chamfer 

        # Get the profiles defined by the circles.
        # profile1 = sketch_SP.profiles.item(0)
        # profile2 = sketch_SP.profiles.item(1)

        # # Get the inner and outer profile
        # areaPropertiesOfProfile1 = profile1.areaProperties()
        # areaPropertiesOfProfile2 = profile2.areaProperties()
        # areaOfProfile1 = areaPropertiesOfProfile1.area
        # areaOfProfile2 = areaPropertiesOfProfile2.area

        # outerProfile = profile1
        # if areaOfProfile1 < areaOfProfile2:
        #     outerProfile = profile2

        ## Add the four edges into a collection
        ##EdgeColl = adsk.core.ObjectCollection.create()
        ##EdgeColl.add(profile1)
        ##EdgeColl.add(sPt1)
        ##EdgeColl.add(sPt2)
        ##EdgeColl.add(sPt3)

        # Get BrepEdge from inner loop on the end face of the extrusion
        # extrudeEndFace = boxBallValvePipe.endFaces.item(0)
        # brepLoops = extrudeEndFace.loops
        # innerLoop = brepLoops.item(0)
        # if innerLoop.isOuter:
        #     innerLoop = brepLoops.item(1)
        # brepEdges = innerLoop.edges
        # brepEdge = brepEdges.item(0)

        # Create the ChamferInput object.
        # chamfers = new_comp.features.chamferFeatures
        # chamferInput = chamfers.createInput2()
        # offset = adsk.core.ValueInput.createByReal(3)
        # chamferInput.chamferEdgeSets.addEqualDistanceChamferEdgeSet(brepEdge, offset, True)
        
        # Create the chamfer.
        # chamfers.add(chamferInput)

        "Lever"
        #Construction Tangent Plane
        # cons_tanPlane_input = new_comp.constructionPlanes.createInput()
        # cons_tanPlane_input.setByTangent(boxBallValvePipe.sideFaces(0), angle=adsk.core.ValueInput.createByReal(0), planarEntity = pipe_sp_profile )  # evt "new_comp.xYConstructionPlane" istedenfor "planarEntity = pipe_sp_profile"
        # cons_tanPlane_input = new_comp.constructionPlanes.add(cons_tanPlane_input)

        #Constuction Plane through three points
        # sketch_SP = new_comp.sketches.add(new_comp.yZConstructionPlane)
        # sketchLines = sketch_SP.sketchCurves.sketchLines
        # point1 = adsk.core.Point3D.create()
       

        "Ball"
        #Construction Offset Plane
        const_offsetPlane_input = new_comp.constructionPlanes.createInput()
        const_offsetPlane_input.setByOffset(planarEntity=pipe_sp_profile, offset=adsk.core.ValueInput.createByReal(self.P/2+87))
        const_offsetPlane = new_comp.constructionPlanes.add(const_offsetPlane_input)
        #Center Point
        center_sp = adsk.core.Point3D.create(0, 0, 0)
        #Sketch
        sketch_SP = new_comp.sketches.add(const_offsetPlane)
        circle_SP = sketch_SP.sketchCurves.sketchCircles
        circle_SP_Ball = circle_SP.addByCenterRadius(centerPoint=center_sp, radius=self._d/2-self._d/10)
        line_halfCircle = sketch_SP.sketchCurves.sketchLines
        line_halfCircle_ball = line_halfCircle.addByTwoPoints(adsk.core.Point3D.create(self._d/2-self._d/10, 0, 0), adsk.core.Point3D.create(-self._d/2+self._d/10, 0, 0))
        #Revolve
        halfCircle_profile = sketch_SP.profiles.item(0)
        revolve_ball = new_comp.features.revolveFeatures.createInput(profile=halfCircle_profile, axis=line_halfCircle_ball, operation=adsk.fusion.FeatureOperations.NewBodyFeatureOperation)        
        revolve_ball.setAngleExtent(False, angle=adsk.core.ValueInput.createByString('360 deg')) 
        bodyBallValveBall = new_comp.features.revolveFeatures.add(revolve_ball)
        #Sketch
        sketch_SP = new_comp.sketches.add(const_offsetPlane)
        circle_SP = sketch_SP.sketchCurves.sketchCircles
        circle_cut_ball = circle_SP.addByCenterRadius(centerPoint=center_sp, radius=self._d/2-self._d/4)
        #Extrude Cut
        circleCut_profile = sketch_SP.profiles.item(0)
        ext_cut_ball = new_comp.features.extrudeFeatures.createInput(profile=circleCut_profile, operation=adsk.fusion.FeatureOperations.CutFeatureOperation)
        ext_cut_ball.setDistanceExtent(isSymmetric=True, distance=adsk.core.ValueInput.createByReal(self._d/2))
        bodyBallValveBallHole = new_comp.features.extrudeFeatures.add(ext_cut_ball)
        "Handle"
        
        
        

        "Top spool piece"
        #Construction Offset Plane
        const_offsetPlane_input = new_comp.constructionPlanes.createInput()
        const_offsetPlane_input.setByOffset(planarEntity=pipe_sp_profile, offset=adsk.core.ValueInput.createByReal(self.P/2+102))
        const_offsetPlane = new_comp.constructionPlanes.add(const_offsetPlane_input)
        #Center Point
        center_sp = adsk.core.Point3D.create(0, 0, 0)
        #Sketch
        sketch_SP = new_comp.sketches.add(const_offsetPlane)
        circle_SP = sketch_SP.sketchCurves.sketchCircles
        circle_SP_o = circle_SP.addByCenterRadius(centerPoint=center_sp, radius=self._d-self._d/10)
        circle_SP_i = circle_SP.addByCenterRadius(centerPoint=center_sp, radius=self._d/2-self._d/10)
        #Extrude
        pipe_SP_profile = sketch_SP.profiles.item(0)
        ext_pipe_SP_input = new_comp.features.extrudeFeatures.createInput(profile=pipe_SP_profile, operation=adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        ext_pipe_SP_input.setDistanceExtent(isSymmetric=True, distance=adsk.core.ValueInput.createByReal(1))
        bodyTwo = new_comp.features.extrudeFeatures.add(ext_pipe_SP_input)
        #Sketch
        parent_sketch = sketch_SP.sketchCurves.sketchCircles.addByCenterRadius(centerPoint=adsk.core.Point3D.create(0,self._d-5,0), radius=2)                  #item(2)
        #Extrude Cut
        spool_profile = sketch_SP.profiles.item(2)
        ext_spool_hole = new_comp.features.extrudeFeatures.createInput(profile=spool_profile, operation=adsk.fusion.FeatureOperations.CutFeatureOperation)
        ext_spool_hole.setDistanceExtent(isSymmetric=True, distance=adsk.core.ValueInput.createByReal(0.2*self._d))
        circle_cut = new_comp.features.extrudeFeatures.add(ext_spool_hole)
        #Circular Pattern
        CircularPatterns = new_comp.features.circularPatternFeatures
        inputEntitiesCollection = adsk.core.ObjectCollection.create()
        inputEntitiesCollection.add(circle_cut)
        inputAxis = const_axis_sp
        CircularPatternInput = CircularPatterns.createInput(inputEntitiesCollection, inputAxis)
        CircularPatternInput.quantity = adsk.core.ValueInput.createByReal(self.H)
        CircularPatternInput.totalAngle = adsk.core.ValueInput.createByString('360 deg')
        CircularPatternInput.isSymmetric = False
        CircularPattern = CircularPatterns.add(CircularPatternInput)

        "Handle base"
        #Construction Plane at angle
        const_plane_sp_input = new_comp.constructionPlanes.createInput()
        const_plane_sp_input.setByAngle(linearEntity=new_comp.xConstructionAxis, angle=adsk.core.ValueInput.createByReal(self.theta+radians(90)), planarEntity=new_comp.xYConstructionPlane)   #self.theta+90
        const_plane_sp = new_comp.constructionPlanes.add(const_plane_sp_input)
        #Sketch circle extrude 1
        sketch_sp = new_comp.sketches.add(const_plane_sp)
        #center_sp = sketch_sp.modelToSketchSpace(center_global)
        circles_sp = sketch_sp.sketchCurves.sketchCircles
        center_box = adsk.core.Point3D.create(-1.218,108.25,-14)
        circle_sp_o = circles_sp.addByCenterRadius(centerPoint=center_box, radius=2.5)
        #Extrude
        pipe_sp_profile = sketch_sp.profiles.item(0)  # get the pipe profile (profile between inner and outer circle)
        ext_pipe_sp_input = new_comp.features.extrudeFeatures.createInput(profile=pipe_sp_profile, operation=adsk.fusion.FeatureOperations.JoinFeatureOperation)
        ext_pipe_sp_input.setDistanceExtent(isSymmetric= True, distance=adsk.core.ValueInput.createByReal(2))
        bodyOne = new_comp.features.extrudeFeatures.add(ext_pipe_sp_input)
        #Sketch cicle extrude 2
        sketch_sp = new_comp.sketches.add(const_plane_sp)
        circles_sp = sketch_sp.sketchCurves.sketchCircles
        center_box = adsk.core.Point3D.create(-1.218,108.25,-14)
        circle_sp_o = circles_sp.addByCenterRadius(centerPoint=center_box, radius=1)
        #Extrude
        pipe_sp_profile = sketch_sp.profiles.item(0)  # get the pipe profile (profile between inner and outer circle)
        ext_pipe_sp_input = new_comp.features.extrudeFeatures.createInput(profile=pipe_sp_profile, operation=adsk.fusion.FeatureOperations.JoinFeatureOperation)
        ext_pipe_sp_input.setDistanceExtent(isSymmetric= True, distance=adsk.core.ValueInput.createByReal(3.5))
        bodyOne = new_comp.features.extrudeFeatures.add(ext_pipe_sp_input)

        "Handle"
        #Sketch on zy-plane
        sketch_SP = new_comp.sketches.add(new_comp.yZConstructionPlane)    #(z,y,x)
        sketchLines = sketch_SP.sketchCurves.sketchLines
        sketchArcs = sketch_SP.sketchCurves.sketchArcs

        posArray = [0,1,2]
        zArray = [-53.5,-50,-51.282,-46]
        yArray = [-100,-90.35,-87.512,-73]

        for i in posArray:
            startPoint = adsk.core.Point3D.create(zArray[i],yArray[i],0)
            endPoint = adsk.core.Point3D.create(zArray[i+1],yArray[i+1],0)
            sketchLines.addByTwoPoints(startPoint,endPoint)

        posArrayOffset = [0,1,2]
        zArrayOff = [-46.7808,-52.137,-50.851,-54.264]
        yArrayOff = [-72.806,-87.523,-90.37,-99.727]

        for i in posArrayOffset:
            startPoint = adsk.core.Point3D.create(zArrayOff[i],yArrayOff[i],0)
            endPoint = adsk.core.Point3D.create(zArrayOff[i+1],yArrayOff[i+1],0)
            sketchLines.addByTwoPoints(startPoint,endPoint)
        
        arcStart = adsk.core.Point3D.create(-46,-73,0)
        arcCenter = adsk.core.Point3D.create(-46.3904,-72.903,0)
        sketchArcs.addByCenterStartSweep(arcCenter,arcStart,radians(180))

        arcStart = adsk.core.Point3D.create(-53.5,-100,0)
        arcCenter = adsk.core.Point3D.create(-53.882,-99.8635,0)
        sketchArcs.addByCenterStartSweep(arcCenter,arcStart,radians(-180))

        #Extrude
        pipe_sp_profile = sketch_sp.profiles.item(0)  
        ext_pipe_sp_input = new_comp.features.extrudeFeatures.createInput(profile=pipe_sp_profile, operation=adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        ext_pipe_sp_input.setDistanceExtent(isSymmetric= True, distance=adsk.core.ValueInput.createByReal(2))
        Handle_ext = new_comp.features.extrudeFeatures.add(ext_pipe_sp_input)



        
# ------------------------------------------------------------------------------

def run(context):
    try:
        # Get the existing command definition or create it if it doesn't already exist.
        cmdDef = ui.commandDefinitions.itemById('FlowValve')
        if not cmdDef:
            cmdDef = ui.commandDefinitions.addButtonDefinition('FlowValve', 'Create Flow-Valve', 'Create a customized flow-valve.', './resources') # relative resource file path is specified

        # Connect to the command created event.
        onCommandCreated = FlowValveCommandCreatedHandler()
        cmdDef.commandCreated.add(onCommandCreated)
        _handlers.append(onCommandCreated)
        inputs = adsk.core.NamedValues.create()

        # Execute the command definition.
        cmdDef.execute(inputs)

        # prevent this module from being terminate when the script returns, because we are waiting for event _handlers to fire
        adsk.autoTerminate(False)
    except:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))
