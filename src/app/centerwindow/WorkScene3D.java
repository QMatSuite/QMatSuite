/*******************************************************************************
 * Copyright (c) 2020 Haonan Huang.
 *
 *     This file is part of QuantumVITAS (Quantum Visualization Interactive Toolkit for Ab-initio Simulations).
 *
 *     QuantumVITAS is free software: you can redistribute it and/or modify
 *     it under the terms of the GNU General Public License as published by
 *     the Free Software Foundation, either version 3 of the License, or
 *     any later version.
 *
 *     QuantumVITAS is distributed in the hope that it will be useful,
 *     but WITHOUT ANY WARRANTY; without even the implied warranty of
 *     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *     GNU General Public License for more details.
 *
 *     You should have received a copy of the GNU General Public License
 *     along with QuantumVITAS.  If not, see <https://www.gnu.org/licenses/gpl-3.0.txt>.
 *******************************************************************************/
package app.centerwindow;

import java.io.IOException;
import java.util.ArrayList;

import com.consts.Constants.EnumUnitAtomPos;
import com.consts.Constants.EnumUnitCellAngle;
import com.consts.Constants.EnumUnitCellParameter;
import com.consts.PhysicalConstants;

import agent.InputAgentGeo;
import app.input.geo.Atom;
import javafx.event.EventHandler;
import javafx.fxml.FXMLLoader;
import javafx.geometry.Insets;
import javafx.geometry.Point3D;
import javafx.scene.Group;
import javafx.scene.Node;
import javafx.scene.PerspectiveCamera;
import javafx.scene.SubScene;
import javafx.scene.control.Alert;
import javafx.scene.control.Alert.AlertType;
import javafx.scene.control.TabPane;
import javafx.scene.input.MouseEvent;
import javafx.scene.input.ScrollEvent;
import javafx.scene.layout.AnchorPane;
import javafx.scene.layout.Background;
import javafx.scene.layout.BackgroundFill;
import javafx.scene.layout.CornerRadii;
import javafx.scene.layout.VBox;
import javafx.scene.paint.Color;
import javafx.scene.paint.PhongMaterial;
import javafx.scene.shape.Box;
import javafx.scene.shape.Cylinder;
import javafx.scene.shape.Sphere;
import javafx.scene.transform.Rotate;
import javafx.scene.transform.Translate;
import math.Thresholds;

public class WorkScene3D {
	private AnchorPane acp;//root
	private VBox hb;//child 1, for toolbar
	private SubScene subScene;//child 2, for 3D scene
	
	private final Group root = new Group();
	private GeoGroup world= new GeoGroup();
	private GeoGroup moleculeGroup= new GeoGroup();
	private Group axisGroup= new Group();
	private final PerspectiveCamera camera = new PerspectiveCamera(true);
	private final GeoGroup cameraSys1 = new GeoGroup();
	private final GeoGroup cameraSys2 = new GeoGroup();
	private final GeoGroup cameraSys3 = new GeoGroup();
	private final double cameraDistance = 1500;

	private final int maxTrialCells = 8;//(maxTrialCells*2)^3 cells tried
	private final double ballRadiusAtom = 30;
	private final int bondThick = 10;
	public  double bondScaling=1.06;//the same across WorkScenes
	private static final double minBondScaling=0.1;
	public InputAgentGeo iGeoCache=null;
	public boolean boolFoldBack=false;
	public int supercellMode = 0;//0 is no, 1 is crystal, 2 is alat, -1 is not selected
	public Integer nx,ny,nz;
	
	private ArrayList<Atom> atomListCacheSC;
        
	private double mousePosX;
	private double mousePosY;
	private double mouseOldX;
	private double mouseOldY;
	private double mouseDeltaX;
	private double mouseDeltaY;
    
    private Toolbar3DController cont3D;
    
    //angstrom/length in the figure
    private double scalingLength;//not good, because it is a global parameter
    
	public WorkScene3D() {
		
		acp = new AnchorPane();
		
		cont3D = new Toolbar3DController(this);
		FXMLLoader fxmlLoader2 = new FXMLLoader(this.getClass().getResource("toolbar3D.fxml"));
		fxmlLoader2.setController(cont3D);
		try {
			hb = fxmlLoader2.load();
		} catch (IOException e) {
			e.printStackTrace();
			Alert alert1 = new Alert(AlertType.INFORMATION);
	    	alert1.setTitle("Error");
	    	alert1.setContentText("Cannot load fxml in WorkScene3D!");
	    	alert1.showAndWait();
	    	return;
		}
		hb.setBackground(new Background(new BackgroundFill(Color.LIGHTGRAY, CornerRadii.EMPTY, Insets.EMPTY)));
		
		buildAxes();//add axes
		
		world.getChildren().addAll(axisGroup,moleculeGroup);
		
		buildCamera();
		root.getChildren().add(world);
		subScene = new SubScene(root, 800, 600, true, null);
		subScene.setFill(Color.SILVER);
		subScene.setCamera(camera);
		//camera.setFieldOfView(20);
		
		acp.getChildren().addAll(subScene,hb);
		handleMouse(subScene, world);
		//initMouseControl();
		//buildSampleMolecule();
	}
	private void buildCamera() {
	    
        root.getChildren().add(cameraSys1);
        cameraSys1.getChildren().add(cameraSys2);
        cameraSys2.getChildren().add(cameraSys3);
        cameraSys3.getChildren().add(camera);
        cameraSys3.rotateAlongZ(0);
 
        camera.setNearClip(0.2);
        camera.setFarClip(25000.0);
        camera.setTranslateZ(-cameraDistance);
        
        cameraSys1.rx.setAngle(-100.0);
        cameraSys1.rz.setAngle(100);
    }
	public void resetCamera() {
		cameraSys2.t.setX(0);
		cameraSys2.t.setY(0);
		camera.setTranslateZ(-cameraDistance);
		cameraSys1.rx.setAngle(-100.0);
        cameraSys1.rz.setAngle(100);
	}
	private void handleMouse(SubScene scene, final Node root) {
        scene.setOnMousePressed(new EventHandler<MouseEvent>() {
            @Override public void handle(MouseEvent me) {
                mousePosX = me.getSceneX();
                mousePosY = me.getSceneY();
                mouseOldX = me.getSceneX();
                mouseOldY = me.getSceneY();
            }
        });
        scene.setOnMouseDragged(new EventHandler<MouseEvent>() {
            @Override public void handle(MouseEvent me) {
                mouseOldX = mousePosX;
                mouseOldY = mousePosY;
                mousePosX = me.getSceneX();
                mousePosY = me.getSceneY();
                mouseDeltaX = (mousePosX - mouseOldX); 
                mouseDeltaY = (mousePosY - mouseOldY); 
                
                double modifier = 1.0;
                double modifierFactor = 0.15;
                
                if (me.isControlDown()) {
                    modifier = 0.1;
                } 
                if (me.isShiftDown()) {
                    modifier = 10.0;
                }     
                if (me.isPrimaryButtonDown()) {
                    cameraSys1.rz.setAngle(cameraSys1.rz.getAngle() - mouseDeltaX*modifierFactor*modifier*2.0);  // +
                    cameraSys1.rx.setAngle(cameraSys1.rx.getAngle() - mouseDeltaY*modifierFactor*modifier*2.0);  // -
                }
                else if (me.isSecondaryButtonDown()) {
                    double z = camera.getTranslateZ();
                    double newZ = z - mouseDeltaX*modifierFactor*modifier;
                    camera.setTranslateZ(newZ);
                }
                else if (me.isMiddleButtonDown()) {
                    cameraSys2.t.setX(cameraSys2.t.getX() + mouseDeltaX*modifierFactor*modifier*0.3);  // -
                    cameraSys2.t.setY(cameraSys2.t.getY() + mouseDeltaY*modifierFactor*modifier*0.3);  // -
                }
            }
        });
        scene.addEventHandler(ScrollEvent.SCROLL, event->{
			double delta = event.getDeltaY();
			camera.translateZProperty().set(camera.getTranslateZ()+delta);
		});
    }
	public void centerSubScene(TabPane workSpaceTabPane) {
//		//bind the width and height of subScene and tabPane
		subScene.heightProperty().bind(workSpaceTabPane.heightProperty());
		subScene.widthProperty().bind(workSpaceTabPane.widthProperty());
//		//bind the group to the center
//		world.translateXProperty().bind(subScene.widthProperty().divide(2));
//		world.translateYProperty().bind(subScene.heightProperty().divide(2));
//		world.translateXProperty().bind(workSpaceTabPane.heightProperty().divide(2));
//		world.translateYProperty().bind(workSpaceTabPane.heightProperty().divide(2));
	}
	public void drawGroup(GeoGroup sg) {
		moleculeGroup.getChildren().clear();
		moleculeGroup.getChildren().add(sg);
	}
	public AnchorPane getRootPane() {
		return acp;
	}
	private void buildAxes() {
		if (axisGroup==null) axisGroup = new Group();
		final double AXIS_LENGTH = 300;
		
        final PhongMaterial materialX = new PhongMaterial();
        materialX.setDiffuseColor(Color.DARKRED);
        materialX.setSpecularColor(Color.RED);
 
        final PhongMaterial materialY = new PhongMaterial();
        materialY.setDiffuseColor(Color.DARKGREEN);
        materialY.setSpecularColor(Color.GREEN);
 
        final PhongMaterial materialZ = new PhongMaterial();
        materialZ.setDiffuseColor(Color.DARKBLUE);
        materialZ.setSpecularColor(Color.BLUE);
 
        final Box xAxis = new Box(AXIS_LENGTH, 1, 1);
        final Box yAxis = new Box(1, AXIS_LENGTH, 1);
        final Box zAxis = new Box(1, 1, AXIS_LENGTH);
        
        xAxis.setMaterial(materialX);
        yAxis.setMaterial(materialY);
        zAxis.setMaterial(materialZ);
 
        axisGroup.getChildren().addAll(xAxis, yAxis, zAxis);
        axisGroup.setVisible(true);
    }
	public void buildGeometry(InputAgentGeo iGeo) {
		if (moleculeGroup==null || iGeo == null) return;
		
		//cache InputAgentGeo to make possible the view changes
		iGeoCache = iGeo;
		
		buildGeometry();
	}
	public void buildGeometry() {
		if (moleculeGroup==null || iGeoCache == null) return;
		
	    //clear world to avoid plotting a lot of things
		moleculeGroup.getChildren().clear();
		
		if(!iGeoCache.ibrav.isNull()) { //a bravais lattice is always necessary!
			
			GeoGroup latticeGroup = new GeoGroup();
			GeoGroup atomsGroup = new GeoGroup();
			GeoGroup bondsGroup = new GeoGroup();

			final double alat = 300;
	        
			//generate lattice vectors
	        Point3D lattVecs[] = genVecFromGeo(alat);
	        if (lattVecs==null) return;//important
	        
	        //draw bravais lattice
	        buildBravaisLattice(alat, lattVecs,latticeGroup);
		
			if(iGeoCache.atomList.size()>0) {
				
				ArrayList<Atom> atomListClone = genAtomListInAlat(alat,lattVecs);
				if (atomListClone==null) return;//important
				
				addAtomsToScene(alat,atomListClone,atomsGroup,lattVecs);
				addBondsToScene(atomListClone,bondsGroup,lattVecs);
			}
			moleculeGroup.getChildren().addAll(latticeGroup, atomsGroup, bondsGroup);
		}
	}
	private Point3D[] genVecFromGeo(Double alat) {
		if (iGeoCache == null) return null;
		
		Point3D aVec = null;
		Point3D bVec = null;
		Point3D cVec = null;
		
		//make sure that cellA exists, which is always necessary! -> except ibrav==0 and not alat
        if (iGeoCache.cellA.isNull() || iGeoCache.cellA.getValue()<=0) {
        	if(iGeoCache.ibrav.equals(0)) {
        		if(iGeoCache.unitCellParameter.equals(EnumUnitCellParameter.alat)) {
        			cont3D.setStatus("Add alat of change unit for user vectors.");return null;
    			}
        	}
        	else {cont3D.setStatus("Always need alat for ibrav not zero.");return null;}
        }
        
        final Double a,b,c,gm,alpha,beta;
        a = alat;
        
        if (!iGeoCache.cellA.isNull() && iGeoCache.cellA.getValue()>0 && !iGeoCache.cellB.isNull()) {
        	b=iGeoCache.cellB.getValue()/iGeoCache.cellA.getValue()*alat;
        }
        else b=null;
        if (!iGeoCache.cellA.isNull() && iGeoCache.cellA.getValue()>0 && !iGeoCache.cellC.isNull()) {
        	c=iGeoCache.cellC.getValue()/iGeoCache.cellA.getValue()*alat;
        }
        else c=null;
        
        if (!iGeoCache.cellAngleAB.isNull()) {
        	if (iGeoCache.unitCellAngle.equals(EnumUnitCellAngle.degree)) gm = Math.toRadians(iGeoCache.cellAngleAB.getValue());
        	else if (iGeoCache.unitCellAngle.equals(EnumUnitCellAngle.radian)) gm = iGeoCache.cellAngleAB.getValue();
        	else gm = null;
    	}
        else gm=null;
        
        if (!iGeoCache.cellAngleAC.isNull()) {
        	if (iGeoCache.unitCellAngle.equals(EnumUnitCellAngle.degree)) beta = Math.toRadians(iGeoCache.cellAngleAC.getValue());
        	else if (iGeoCache.unitCellAngle.equals(EnumUnitCellAngle.radian)) beta = iGeoCache.cellAngleAC.getValue();
        	else beta = null;
    	}
        else beta=null;
        
        if (!iGeoCache.cellAngleBC.isNull()) {
        	if (iGeoCache.unitCellAngle.equals(EnumUnitCellAngle.degree)) alpha = Math.toRadians(iGeoCache.cellAngleBC.getValue());
        	else if (iGeoCache.unitCellAngle.equals(EnumUnitCellAngle.radian)) alpha = iGeoCache.cellAngleBC.getValue();
        	else alpha = null;
    	}
        else alpha=null;
        
        //get the scaling for later use
        double scalingTmp;
        if (iGeoCache.ibrav.equals(0)) {//user defined lattice parameters
        	if (iGeoCache.vectorA1.isNull() || iGeoCache.vectorA2.isNull() || iGeoCache.vectorA3.isNull()
        			|| iGeoCache.vectorB1.isNull() || iGeoCache.vectorB2.isNull() || iGeoCache.vectorB3.isNull()
        			|| iGeoCache.vectorC1.isNull() || iGeoCache.vectorC2.isNull() || iGeoCache.vectorC3.isNull()) {
        		return null;
        	}
        	else {
        		double lengthA = Math.sqrt(Math.pow(iGeoCache.vectorA1.getValue(), 2)+Math.pow(iGeoCache.vectorA2.getValue(), 2)+Math.pow(iGeoCache.vectorA3.getValue(), 2));
        		double lengthB = Math.sqrt(Math.pow(iGeoCache.vectorB1.getValue(), 2)+Math.pow(iGeoCache.vectorB2.getValue(), 2)+Math.pow(iGeoCache.vectorB3.getValue(), 2));
        		double lengthC = Math.sqrt(Math.pow(iGeoCache.vectorC1.getValue(), 2)+Math.pow(iGeoCache.vectorC2.getValue(), 2)+Math.pow(iGeoCache.vectorC3.getValue(), 2));
        		if (lengthA==0 || lengthB==0 || lengthC==0) return null;
        		
        		double mx = Math.max(Math.max(lengthA, lengthB), lengthC);//do not change. If change, please change everywhere in this program
        		double scalingAll = a/mx;
        		aVec= new Point3D(iGeoCache.vectorA1.getValue(),iGeoCache.vectorA2.getValue(),iGeoCache.vectorA3.getValue()).multiply(scalingAll); 
	        	bVec= new Point3D(iGeoCache.vectorB1.getValue(),iGeoCache.vectorB2.getValue(),iGeoCache.vectorB3.getValue()).multiply(scalingAll); 
	        	cVec= new Point3D(iGeoCache.vectorC1.getValue(),iGeoCache.vectorC2.getValue(),iGeoCache.vectorC3.getValue()).multiply(scalingAll); 
	        	
	        	double det = -aVec.getZ()*bVec.getY()*cVec.getX() + aVec.getY()*bVec.getZ()*cVec.getX() 
        				+ aVec.getZ()*bVec.getX()*cVec.getY() - aVec.getX()*bVec.getZ()*cVec.getY() 
        				- aVec.getY()*bVec.getX()*cVec.getZ() + aVec.getX()*bVec.getY()*cVec.getZ();
	        	if (Math.abs(det) < Thresholds.zero*mx) return null;//then a,b,cVec are in the same plane (or almost)
	        	
	        	scalingTmp = 1.0/a*mx;
	        	
	        	switch(iGeoCache.unitCellParameter){//aUnit
					case alat:
						//iGeoCache.cellA must exist and >0, because previous steps ensured that
						scalingTmp = scalingTmp*iGeoCache.cellA.getValue();
						switch(iGeoCache.unitCellLength) {//the unit of iGeoCache.cellA
							case angstrom:break;
							case bohr:scalingTmp = scalingTmp*PhysicalConstants.angstPerBohr;break;
							case pm:scalingTmp = scalingTmp/100;break;
							default:
								Alert alert1 = new Alert(AlertType.INFORMATION);
						    	alert1.setTitle("Error");
						    	alert1.setContentText("Non valid unitCellLength detected in WorkScene3D!");
						    	alert1.showAndWait();
								return null;
						}
						break;
					case angstrom:
						break;
					case bohr:
						scalingTmp=scalingTmp*PhysicalConstants.angstPerBohr;break;
					case pm:
						scalingTmp=scalingTmp/100;break;
					default:
						Alert alert1 = new Alert(AlertType.INFORMATION);
				    	alert1.setTitle("Error");
				    	alert1.setContentText("Non valid unitCellParameter detected in WorkScene3D!");
				    	alert1.showAndWait();
						return null;
	    		}
	        	scalingLength = scalingTmp;
        	}
		}
		else {//ibrav not 0, then iGeoCache.cellA must exist and >0, because previous steps ensured that
			scalingTmp = 1.0/alat*iGeoCache.cellA.getValue();
			switch(iGeoCache.unitCellLength){//aUnit
				case bohr:scalingTmp=scalingTmp*PhysicalConstants.angstPerBohr;break;
				case angstrom:break;
				case pm:scalingTmp=scalingTmp/100;break;
				default:
					Alert alert1 = new Alert(AlertType.INFORMATION);
			    	alert1.setTitle("Error");
			    	alert1.setContentText("Non valid unitCellLength detected in WorkScene3D!");
			    	alert1.showAndWait();
					return null;
			}
			scalingLength = scalingTmp;
		}
        
        switch (iGeoCache.ibrav.getValue()) {
        case 0:
        	break;
        case 1://sc
        	aVec= new Point3D(1,0,0).multiply(a); 
        	bVec= new Point3D(0,1,0).multiply(a); 
        	cVec= new Point3D(0,0,1).multiply(a); 
	        break;
        case 2://fcc
        	aVec= new Point3D(-1,0,1).multiply(a/2); 
        	bVec= new Point3D(0,1,1).multiply(a/2); 
        	cVec= new Point3D(-1,1,0).multiply(a/2); 
//        	aVec= new Point3D(1,0,1).multiply(a/2); 
//        	bVec= new Point3D(0,1,1).multiply(a/2); 
//        	cVec= new Point3D(1,1,0).multiply(a/2); 
        	break;
        case 3://bcc
        	aVec= new Point3D(1,1,1).multiply(a/2); 
        	bVec= new Point3D(-1,1,1).multiply(a/2); 
        	cVec= new Point3D(-1,-1,1).multiply(a/2); 
//        	aVec= new Point3D(1,1,-1).multiply(a/2); 
//        	bVec= new Point3D(-1,1,1).multiply(a/2); 
//        	cVec= new Point3D(1,-1,1).multiply(a/2); 
        	break;
        case 4:
        	if (c==null) return null;
        	aVec= new Point3D(a,0,0); 
        	bVec= new Point3D(-1,Math.sqrt(3),0).multiply(a/2); 
        	cVec= new Point3D(0,0,c); 
        	break;
        case 5://trigonal R, still not good
        	if (gm==null) return null; //gamma
        	double tx=Math.sqrt((1-Math.cos(gm))/2);
        	double ty=Math.sqrt((1-Math.cos(gm))/6);
        	double tz=Math.sqrt((1+2*Math.cos(gm))/3);
        	aVec= new Point3D(tx,-ty,tz).multiply(alat); 
        	bVec= new Point3D(0,2*ty,tz).multiply(alat); 
        	cVec= new Point3D(-tx,-ty,tz).multiply(alat); 
        	break;
        case 6:
        	if (c==null) return null;
        	aVec= new Point3D(a,0,0); 
        	bVec= new Point3D(0,a,0); 
        	cVec= new Point3D(0,0,c); 
        	break;
        case 7://Tetragonal I (bct)
        	if (c==null) return null;
        	aVec= new Point3D(1,-1,c/a).multiply(a/2); 
        	bVec= new Point3D(1,1,c/a).multiply(a/2); 
        	cVec= new Point3D(-1,-1,c/a).multiply(a/2);
//        	aVec= new Point3D(1,1,-c/a).multiply(a/2); 
//        	bVec= new Point3D(1,-1,c/a).multiply(a/2); 
//        	cVec= new Point3D(-1,1,c/a).multiply(a/2); 
        	break;
        case 8:
        	if (b==null || c==null) return null;
        	aVec= new Point3D(a,0,0); 
        	bVec= new Point3D(0,b,0); 
        	cVec= new Point3D(0,0,c); 
        	break;
        case 9:
        	if (b==null || c==null) return null;
        	aVec= new Point3D(a/2,b/2,0); 
        	bVec= new Point3D(-a/2,b/2,0); 
        	cVec= new Point3D(0,0,c); 
        	break;
        case 10:
        	if (b==null || c==null) return null;
        	aVec= new Point3D(a/2,0,c/2); 
        	bVec= new Point3D(a/2,b/2,0); 
        	cVec= new Point3D(0,b/2,c/2); 
        	break;
        case 11:
        	if (b==null || c==null) return null;
        	aVec= new Point3D(a/2,b/2,c/2); 
        	bVec= new Point3D(-a/2,b/2,c/2);  
        	cVec= new Point3D(-a/2,-b/2,c/2); 
        	break;
        case 12:
        	if (b==null || c==null || gm==null) return null;
        	aVec= new Point3D(a,0,0); 
        	bVec= new Point3D(Math.cos(gm),Math.sin(gm),0).multiply(b); 
        	cVec= new Point3D(0,0,c); 
        	break;
        case 13:
        	if (b==null || c==null || gm==null) return null;
        	aVec= new Point3D(a/2,0,-c/2); 
        	bVec= new Point3D(b*Math.cos(gm), b*Math.sin(gm), 0); 
        	cVec= new Point3D(a/2,0,c/2); 
        	break;
        case 14:
        	if (b==null || c==null || gm==null
        			|| beta==null || alpha==null) return null;
        	aVec= new Point3D(a,0,0); 
        	bVec= new Point3D(b*Math.cos(gm), b*Math.sin(gm), 0); 
        	cVec= new Point3D(c*Math.cos(beta),  
        		   c*(Math.cos(alpha)-Math.cos(beta)*Math.cos(gm))/Math.sin(gm),
	        	   c*Math.sqrt( 1 + 2*Math.cos(alpha)*Math.cos(beta)*Math.cos(gm)
	        	   - Math.pow(Math.cos(alpha), 2)-Math.pow(Math.cos(beta), 2)
	        	   -Math.pow(Math.cos(gm), 2) )/Math.sin(gm) ); 
        	break;
        default:
			Alert alert1 = new Alert(AlertType.INFORMATION);
	    	alert1.setTitle("Error");
	    	alert1.setContentText("Non existing ibrav detected in WorkScene3D!");

	    	alert1.showAndWait();
        	return null;
        }
        Point3D out[] = {aVec,bVec,cVec};
        return out;
	}
	private void buildBravaisLattice(double alat, Point3D[] lattVecs,GeoGroup latticeGroup) {
		
        
        final int thick = 1;
        
		Point3D origin = new Point3D(0,0,0);
		
		Point3D aVec=lattVecs[0];
        Point3D bVec=lattVecs[1];
        Point3D cVec=lattVecs[2];
        
        final PhongMaterial material = new PhongMaterial();
        material.setDiffuseColor(Color.DARKBLUE);
        material.setSpecularColor(Color.LIGHTBLUE);
        
        //supercellMode 0 is no, 1 is crystal, 2 is alat, -1 is not selected (null)
    	int nxlim=1;
    	int nylim=1;
    	int nzlim=1;
    	
        if (supercellMode==0) {}
        else if (supercellMode==1) {
        	if (nx==null||ny==null||nz==null) {cont3D.setStatus("No nx,ny,nz!");return;}
        	if (nx>0 && ny>0 && nz>0) {nxlim=nx;nylim=ny;nzlim=nz;}
    	}
        else if (supercellMode==2) {
        	if (nx==null||ny==null||nz==null || nx<=0 || ny<=0 || nz<=0) {cont3D.setStatus("No nx,ny,nz!");return;}
        	
        	Cylinder x1,x2,x3,x4,y1,y2,y3,y4,z1,z2,z3,z4;
			
	        x1 = makeCylinderConnect(new Point3D(0,0,0),new Point3D(alat*nx,0,0),thick);
	        x2 = makeCylinderConnect(new Point3D(0,0,0),new Point3D(0,alat*ny,0),thick);
	        x3 = makeCylinderConnect(new Point3D(0,0,0),new Point3D(0,0,alat*nz),thick);
	        
	        y1 = makeCylinderConnect(new Point3D(alat*nx,0,0),new Point3D(alat*nx,0,alat*nz),thick);
	        y2 = makeCylinderConnect(new Point3D(alat*nx,0,0),new Point3D(alat*nx,alat*ny,0),thick);
	        
	        y3 = makeCylinderConnect(new Point3D(0,alat*ny,0),new Point3D(0,alat*ny,alat*nz),thick);
	        y4 = makeCylinderConnect(new Point3D(0,alat*ny,0),new Point3D(alat*nx,alat*ny,0),thick);
	        
	        z1 = makeCylinderConnect(new Point3D(alat*nx,alat*ny,alat*nz),new Point3D(alat*nx,0,alat*nz),thick);
	        z2 = makeCylinderConnect(new Point3D(alat*nx,alat*ny,alat*nz),new Point3D(0,alat*ny,alat*nz),thick);
	        
	        z3 = makeCylinderConnect(new Point3D(alat*nx,alat*ny,alat*nz),new Point3D(alat*nx,alat*ny,0),thick);
	        
	        z4 = makeCylinderConnect(new Point3D(0,0,alat*nz),new Point3D(alat*nx,0,alat*nz),thick);
	        x4 = makeCylinderConnect(new Point3D(0,0,alat*nz),new Point3D(0,alat*ny,alat*nz),thick);
	        
	        if(x1==null || x2==null || x3==null || x4==null || y1==null || y2==null || y3==null || y4==null ||
	        		z1==null || z2==null || z3==null ||  z4==null) {return;}
	        
	        x1.setMaterial(material);x2.setMaterial(material);x3.setMaterial(material);x4.setMaterial(material);
	        y1.setMaterial(material);y2.setMaterial(material);y3.setMaterial(material);y4.setMaterial(material);
	        z1.setMaterial(material);z2.setMaterial(material);z3.setMaterial(material);z4.setMaterial(material);
	        
	        latticeGroup.getChildren().addAll(x1,x2,x3,x4,y1,y2,y3,y4,z1,z2,z3,z4);
	        latticeGroup.setVisible(true);
	        
        	return;
        }
        else {
        	Alert alert1 = new Alert(AlertType.INFORMATION);
	    	alert1.setTitle("Error");
	    	alert1.setContentText("SupercellMode wrong: "+supercellMode);

	    	alert1.showAndWait();
        	return;
        }
        //***********not a good algorithm, because 4* redundancy
        for (int ix=0 ;ix < nxlim ; ix++) {
        	for (int iy=0 ;iy < nylim ; iy++) {
        		for (int iz=0 ;iz < nzlim ; iz++) {
        			Cylinder x1,x2,x3,x4,y1,y2,y3,y4,z1,z2,z3,z4;
        			
        			Point3D pointOriginNew = new Point3D(0,0,0).add(aVec.multiply(ix)).add(bVec.multiply(iy)).add(cVec.multiply(iz));
        			
			        x1 = makeCylinderConnect(origin.add(pointOriginNew),aVec.add(pointOriginNew),thick);
			        x2 = makeCylinderConnect(bVec.add(pointOriginNew),aVec.add(bVec).add(pointOriginNew),thick);
			        x3 = makeCylinderConnect(cVec.add(pointOriginNew),aVec.add(cVec).add(pointOriginNew),thick);
			        x4 = makeCylinderConnect(bVec.add(cVec).add(pointOriginNew),aVec.add(bVec.add(cVec)).add(pointOriginNew),thick);
			        
			        y1 = makeCylinderConnect(origin.add(pointOriginNew),bVec.add(pointOriginNew),thick);
			        y2 = makeCylinderConnect(aVec.add(pointOriginNew),bVec.add(aVec).add(pointOriginNew),thick);
			        y3 = makeCylinderConnect(cVec.add(pointOriginNew),bVec.add(cVec).add(pointOriginNew),thick);
			        y4 = makeCylinderConnect(aVec.add(cVec).add(pointOriginNew),bVec.add(aVec.add(cVec)).add(pointOriginNew),thick);
			        
			        z1 = makeCylinderConnect(origin.add(pointOriginNew),cVec.add(pointOriginNew),thick);
			        z2 = makeCylinderConnect(bVec.add(pointOriginNew),cVec.add(bVec).add(pointOriginNew),thick);
			        z3 = makeCylinderConnect(aVec.add(pointOriginNew),cVec.add(aVec).add(pointOriginNew),thick);
			        z4 = makeCylinderConnect(bVec.add(aVec).add(pointOriginNew),cVec.add(bVec.add(aVec)).add(pointOriginNew),thick);
			        
			        if(x1==null || x2==null || x3==null || x4==null || y1==null || y2==null || y3==null || y4==null ||
			        		z1==null || z2==null || z3==null ||  z4==null) {continue;}
			        
			        x1.setMaterial(material);x2.setMaterial(material);x3.setMaterial(material);x4.setMaterial(material);
			        y1.setMaterial(material);y2.setMaterial(material);y3.setMaterial(material);y4.setMaterial(material);
			        z1.setMaterial(material);z2.setMaterial(material);z3.setMaterial(material);z4.setMaterial(material);
			        //
			        latticeGroup.getChildren().addAll(x1,x2,x3,x4,y1,y2,y3,y4,z1,z2,z3,z4);
			        latticeGroup.setVisible(true);
        		}
        	}
        }
        
        
	}
	private ArrayList<Atom> genAtomListInAlat(Double alat,Point3D[] outPoint) {
		if (iGeoCache == null) return null;
		
		//deep copy manually
		ArrayList<Atom> atomListClone = new ArrayList<Atom>();
		
		Point3D aVec=outPoint[0];
        Point3D bVec=outPoint[1];
        Point3D cVec=outPoint[2];
        
		for (int i=0;i<iGeoCache.atomList.size();i++) {
			Atom tmp = iGeoCache.atomList.get(i);
			atomListClone.add(
					new Atom(tmp.getAtomSpecies(), tmp.getXcoor().getX(), tmp.getYcoor().getX(),
					tmp.getZcoor().getX(),false,false,false)
					);
//			//to transform to the usual way of 3D viewing
//			atomListClone.add(
//					new Atom(tmp.getAtomSpecies(), tmp.getX_coor().getX(),-tmp.getZ_coor().getX() ,
//					-tmp.getY_coor().getX(),false,false,false)
//					);
//			);
		}
		//draw atoms
		//iGeo.unitCellParameter
		//alat,bohr,angstrom,pm
		switch(iGeoCache.unitAtomPos){//there is a default value, so shouldn't be null
			//alat,bohr,angstrom,crystal
			case alat:
				//necessary, for user defined vectors
				if(iGeoCache.cellA.isNull() || iGeoCache.cellA.getValue()<=0) {cont3D.setStatus("Need alat to plot atoms!");return null;}
				
				
				
				if(iGeoCache.ibrav.equals(0)) {
					double scalingTmp = iGeoCache.cellA.getValue();
					switch(iGeoCache.unitCellLength) {//the unit of iGeoCache.cellA
						case angstrom:break;
						case bohr:scalingTmp = scalingTmp*PhysicalConstants.angstPerBohr;break;
						case pm:scalingTmp = scalingTmp/100;break;
						default:
							Alert alert1 = new Alert(AlertType.INFORMATION);
					    	alert1.setTitle("Error");
					    	alert1.setContentText("Non valid unitCellLength detected in WorkScene3D!");
					    	alert1.showAndWait();
							return null;
					}
					for (int i=0;i<atomListClone.size();i++) {
						atomListClone.get(i).mulX(scalingTmp/scalingLength);
						atomListClone.get(i).mulY(scalingTmp/scalingLength);
						atomListClone.get(i).mulZ(scalingTmp/scalingLength);
					}
				}
				else {
					for (int i=0;i<atomListClone.size();i++) {
						atomListClone.get(i).mulX(alat);
						atomListClone.get(i).mulY(alat);
						atomListClone.get(i).mulZ(alat);
					}
				}
				break;
			case crystal:
				double vtmp1,
				vtmp2,
				vtmp3;
				
				Point3D vout;
				for (int i=0;i<atomListClone.size();i++) {
					vtmp1=atomListClone.get(i).getXcoor().getX();
					vtmp2=atomListClone.get(i).getYcoor().getX();
					vtmp3=atomListClone.get(i).getZcoor().getX();
					
					vout=(aVec.multiply(vtmp1)).add(bVec.multiply(vtmp2)).add(cVec.multiply(vtmp3));
					atomListClone.get(i).getXcoor().setX(vout.getX());
					atomListClone.get(i).getYcoor().setX(vout.getY());
					atomListClone.get(i).getZcoor().setX(vout.getZ());
				}
				break;
			case angstrom:
			case bohr:	
				double scalingTmp=1.0;
				if(iGeoCache.unitAtomPos.equals(EnumUnitAtomPos.angstrom)) scalingTmp = 1.0;
				else if (iGeoCache.unitAtomPos.equals(EnumUnitAtomPos.bohr)) scalingTmp = PhysicalConstants.angstPerBohr;
				
				if(scalingLength<=0) return null;
				for (int i=0;i<atomListClone.size();i++) {
					atomListClone.get(i).mulX(scalingTmp/scalingLength);
					atomListClone.get(i).mulY(scalingTmp/scalingLength);
					atomListClone.get(i).mulZ(scalingTmp/scalingLength);
				}
				break;
			default:
				Alert alert1 = new Alert(AlertType.INFORMATION);
		    	alert1.setTitle("Error");
		    	alert1.setContentText("Non valid unitLength detected in WorkScene3D!");

		    	alert1.showAndWait();
	        	return null;
				
		}
		return atomListClone;
	}
	private void addAtomsToScene(double alat, ArrayList<Atom> atomListClone,GeoGroup atomsGroup,Point3D[] lattVecs) {
		//for supercells
		//supercellMode 0 is no, 1 is crystal, 2 is alat
    	int nxlim=1;
    	int nylim=1;
    	int nzlim=1;
    	
        if (supercellMode==0) {}
        else if (supercellMode==1) {
        	if (nx==null||ny==null||nz==null) {cont3D.setStatus("No nx,ny,nz!");return;}
        	if (nx>0 && ny>0 && nz>0) {nxlim=nx;nylim=ny;nzlim=nz;}
    	}
        else if (supercellMode==2) {
        	if (nx==null||ny==null||nz==null) {cont3D.setStatus("No nx,ny,nz!");return;}
        	if (nx>0 && ny>0 && nz>0) 
        	{
        		Point3D coorRef = cart2crystal(new Point3D(0,0,0), lattVecs[0], lattVecs[1], lattVecs[2]);//just (0,0,0)
        		
//        		Alert alert1 = new Alert(AlertType.INFORMATION);
//		    	alert1.setTitle("Info");
//		    	alert1.setContentText(String.valueOf(coorRef.getX())+" "+String.valueOf(coorRef.getY())+" "+String.valueOf(coorRef.getZ()));
//		    	alert1.showAndWait();
		    	
        		Point3D corr [] = new Point3D[7];
        		corr[0] = cart2crystal(new Point3D(alat*nx,0,0), lattVecs[0], lattVecs[1], lattVecs[2]);
        		corr[1] = cart2crystal(new Point3D(0,alat*ny,0), lattVecs[0], lattVecs[1], lattVecs[2]);
        		corr[2] = cart2crystal(new Point3D(0,0,alat*nz), lattVecs[0], lattVecs[1], lattVecs[2]);
        		corr[3] = cart2crystal(new Point3D(alat*nx,alat*ny,0), lattVecs[0], lattVecs[1], lattVecs[2]);
        		corr[4] = cart2crystal(new Point3D(0,alat*ny,alat*nz), lattVecs[0], lattVecs[1], lattVecs[2]);
        		corr[5] = cart2crystal(new Point3D(alat*nx,0,alat*nz), lattVecs[0], lattVecs[1], lattVecs[2]);
        		corr[6] = cart2crystal(new Point3D(alat*nx,alat*ny,alat*nz), lattVecs[0], lattVecs[1], lattVecs[2]);
        		double distMax = 0;
        		for (int ii=0;ii<7;ii++) {
        			distMax = Math.max(distMax, corr[ii].distance(coorRef));
        		}
        		 
        		//*******not the best algorithm. Performs not good when the primitive cell is very anisotropic
        		//*******also many xiangxian no use
        		nxlim=(int) Math.ceil(distMax);nylim=(int) Math.ceil(distMax);nzlim=(int) Math.ceil(distMax);
        		
        		//tell the user that it is truncated
        		if(nxlim>maxTrialCells || nylim>maxTrialCells || nzlim>maxTrialCells) {
        			cont3D.setStatus("Warning! Atoms truncated.");
        		}
        		
        		nxlim=Math.min(nxlim, maxTrialCells);
        		nylim=Math.min(nylim, maxTrialCells);
        		nzlim=Math.min(nzlim, maxTrialCells);
        		
        		
        		
        		//to shift half later
        		nxlim=2*nxlim;nylim=2*nylim;nzlim=2*nzlim;
        		
        	}
    	}
        else {
        	Alert alert1 = new Alert(AlertType.INFORMATION);
	    	alert1.setTitle("Error");
	    	alert1.setContentText("SupercellMode wrong: "+supercellMode);

	    	alert1.showAndWait();
        	return;
        }
        if (supercellMode==2) {
        	atomListCacheSC = new ArrayList<Atom>();
        }
		//now we can start adding atoms using the normalized positions in the list atomListClone
		for (int i=0;i<atomListClone.size();i++) {
			
			PhongMaterial atomMat = new PhongMaterial();
			atomMat.setSpecularColor(Color.LIGHTGRAY);
			atomMat.setDiffuseColor(Color.web(atomListClone.get(i).getAtomSpecies().getColorJmol()));
			
			double vx = atomListClone.get(i).getXcoor().getX();
			double vy = atomListClone.get(i).getYcoor().getX();
			double vz = atomListClone.get(i).getZcoor().getX();
			//checkFoldBack
			if (boolFoldBack) {
				//folded into the primitive unit cell
				Point3D outFold= foldBack(vx, vy, vz, lattVecs[0], lattVecs[1], lattVecs[2]);
				if (outFold!=null) {
					vx = outFold.getX();
					vy = outFold.getY();
					vz = outFold.getZ();
				}
			}
	        for (int ix=0 ;ix < nxlim ; ix++) {
	        	for (int iy=0 ;iy < nylim ; iy++) {
	        		for (int iz=0 ;iz < nzlim ; iz++) {
	        			Sphere tmpAtom = new Sphere(ballRadiusAtom);
	        			tmpAtom.setMaterial(atomMat);
	        			
	        			Point3D pointOriginNew;
	        			if (supercellMode==2) {
	        				pointOriginNew = new Point3D(0,0,0).add(lattVecs[0].multiply(ix-nxlim/2)).add(lattVecs[1].multiply(iy-nxlim/2)).add(lattVecs[2].multiply(iz-nxlim/2));
	        				//do not plot the ones outside of the bonds
	        				if (nx==null||ny==null||nz==null) {cont3D.setStatus("No nx,ny,nz!");return;}//should not happen
	        				if (vx+pointOriginNew.getX()>nx*alat || vx+pointOriginNew.getX()<0 ||
	        						vy+pointOriginNew.getY()>ny*alat || vy+pointOriginNew.getY()<0 ||
	        						vz+pointOriginNew.getZ()>nz*alat || vz+pointOriginNew.getZ()<0)
	        				{continue;}
	        				else {
	        					atomListCacheSC.add(
        								new Atom(atomListClone.get(i).getAtomSpecies(), vx+pointOriginNew.getX(), vy+pointOriginNew.getY(),
        										vz+pointOriginNew.getZ(),false,false,false));
	        				}
	        			}
	        			else {
	        				pointOriginNew = new Point3D(0,0,0).add(lattVecs[0].multiply(ix)).add(lattVecs[1].multiply(iy)).add(lattVecs[2].multiply(iz));
	        			}
						
	        			tmpAtom.setTranslateX(vx+pointOriginNew.getX());
						tmpAtom.setTranslateY(vy+pointOriginNew.getY());
						tmpAtom.setTranslateZ(vz+pointOriginNew.getZ());
						atomsGroup.getChildren().add(tmpAtom);
	        		}
	        	}
	        }
		}
	}
	private void addBondsToScene(ArrayList<Atom> tmpAtmLst,GeoGroup bondsGroup,Point3D[] lattVecs) {
		if (iGeoCache == null) return;
		
		//add bonds
		cont3D.setStatus("");
		int countBondsTooClose = 0;
		//for supercells
		//supercellMode 0 is no, 1 is crystal, 2 is alat
    	int nxlim=1;
    	int nylim=1;
    	int nzlim=1;
    	int bufferRegion=0;
    	
    	ArrayList<Atom> atomListClone = tmpAtmLst;
    	
        if (supercellMode==0) {}//only explore 0
        //bufferRegion only explore 0,+1,-1 supercell for bonds
        else if (supercellMode==1) {if (nx==null||ny==null||nz==null) {cont3D.setStatus("No nx,ny,nz!");return;}
        if (nx>0 && ny>0 && nz>0) {nxlim=nx;nylim=ny;nzlim=nz;bufferRegion=1;}
        }
        else if (supercellMode==2) {//only explore 0
        	if (atomListCacheSC==null) {cont3D.setStatus("No atomListCacheSC!");return;}
        	else {atomListClone=atomListCacheSC;}
        	}
        else {
        	Alert alert1 = new Alert(AlertType.INFORMATION);
	    	alert1.setTitle("Error");
	    	alert1.setContentText("SupercellMode wrong: "+supercellMode);

	    	alert1.showAndWait();
        	return;
        }
        for (int ix=0 ;ix < nxlim ; ix++) {for (int iy=0 ;iy < nylim ; iy++) {for (int iz=0 ;iz < nzlim ; iz++) {
        	Point3D origini= new Point3D(0,0,0).add(lattVecs[0].multiply(ix)).add(lattVecs[1].multiply(iy)).add(lattVecs[2].multiply(iz));
	        //*********double counting!
			for (int i=0;i<atomListClone.size();i++) {
				for (int j=0;j<atomListClone.size();j++) 
				{for (int sjx=-bufferRegion;sjx<=bufferRegion;sjx++) 
				{for (int sjy=-bufferRegion;sjy<=bufferRegion;sjy++) 
				{for (int sjz=-bufferRegion;sjz<=bufferRegion;sjz++) 
				{
					if (0==sjx && 0==sjy && 0==sjz && i==j) continue;
					//to eliminate the bonds outside of the boundary
					if (ix+sjx<0) continue;
					if (ix+sjx>=nxlim) continue;
					if (iy+sjy<0) continue;
					if (iy+sjy>=nylim) continue;
					if (iz+sjz<0) continue;
					if (iz+sjz>=nzlim) continue;
					
					double vix = atomListClone.get(i).getXcoor().getX();
					double viy = atomListClone.get(i).getYcoor().getX();
					double viz = atomListClone.get(i).getZcoor().getX();
					double vjx = atomListClone.get(j).getXcoor().getX();
					double vjy = atomListClone.get(j).getYcoor().getX();
					double vjz = atomListClone.get(j).getZcoor().getX();
					
					if (boolFoldBack && supercellMode!=2) {
						//folded into the primitive unit cell
						Point3D outi= foldBack(vix, viy, viz, lattVecs[0], lattVecs[1], lattVecs[2]);
						Point3D outj= foldBack(vjx, vjy, vjz, lattVecs[0], lattVecs[1], lattVecs[2]);
						if (outi!=null) {vix = outi.getX();viy = outi.getY();viz = outi.getZ();}
						if (outj!=null) {vjx = outj.getX();vjy = outj.getY();vjz = outj.getZ();}
					}
					
					Point3D originj= new Point3D(0,0,0).add(lattVecs[0].multiply(sjx)).add(lattVecs[1].multiply(sjy)).add(lattVecs[2].multiply(sjz));
					
					vjx += originj.getX();
					vjy += originj.getY();
					vjz += originj.getZ();
					
					Point3D tmpOrigin = new Point3D(vix,viy,viz).add(origini);
					Point3D tmpTarget = new Point3D(vjx,vjy,vjz).add(origini);
					
					double tmpDistance = tmpOrigin.distance(tmpTarget)*scalingLength*100;//convert tmpDistance to pm
					
					double tmpBondLength = atomListClone.get(i).getAtomSpecies().getEmpricalRadius()+
							atomListClone.get(j).getAtomSpecies().getEmpricalRadius();
					
					if (tmpDistance<tmpBondLength*minBondScaling) {
						countBondsTooClose +=1;
						cont3D.setStatus(countBondsTooClose+" bonds too short");
					}
					if (tmpDistance<tmpBondLength*bondScaling) {
						
						//bondsGroup.getChildren().add(makeCylinderConnect(tmpOrigin, tmpTarget,bondThick));
						bondsGroup.getChildren().add(makeTwoColorBond(tmpOrigin, tmpTarget, 
								atomListClone.get(i).getAtomSpecies().getColorJmol(), 
								atomListClone.get(j).getAtomSpecies().getColorJmol()));
					}
				}}}}
			}
        }}}
	}
	private Point3D cart2crystal(Point3D cartCoor, Point3D aVec, Point3D bVec, Point3D cVec) {
		double vx = cartCoor.getX();
		double vy = cartCoor.getY();
		double vz = cartCoor.getZ();
		
		//***********not efficient because every time det is calculated again
		double det = -aVec.getZ()*bVec.getY()*cVec.getX() + aVec.getY()*bVec.getZ()*cVec.getX() 
				+ aVec.getZ()*bVec.getX()*cVec.getY() - aVec.getX()*bVec.getZ()*cVec.getY() 
				- aVec.getY()*bVec.getX()*cVec.getZ() + aVec.getX()*bVec.getY()*cVec.getZ();
		
		if (det!=0.0) {
			//folded into the primitive unit cell
			double ka = 1/det*((-bVec.getZ()*cVec.getY() + bVec.getY()*cVec.getZ())*vx + (bVec.getZ()*cVec.getX() - 
				    bVec.getX()*cVec.getZ())*vy + (-bVec.getY()* cVec.getX() + bVec.getX()*cVec.getY())*vz);
			double kb = 1/det*((aVec.getZ()*cVec.getY() - aVec.getY()* cVec.getZ())*vx + (-aVec.getZ()*cVec.getX() + 
				    aVec.getX()*cVec.getZ())*vy + (aVec.getY()* cVec.getX() - aVec.getX()*cVec.getY())*vz);
			double kc = 1/det*((-aVec.getZ()*bVec.getY() + aVec.getY()* bVec.getZ())*vx + (aVec.getZ()*bVec.getX() - 
				    aVec.getX()*bVec.getZ())*vy + (-aVec.getY()* bVec.getX() + aVec.getX()* bVec.getY())*vz);
			
			Point3D outCryst = new Point3D(ka,kb,kc);
			
			return outCryst;
		}
		else return null;
	}
	private Point3D foldBack(double vx, double vy, double vz, Point3D aVec, Point3D bVec, Point3D cVec) {
		//***********not efficient because every time det is calculated again
		double det = -aVec.getZ()*bVec.getY()*cVec.getX() + aVec.getY()*bVec.getZ()*cVec.getX() 
				+ aVec.getZ()*bVec.getX()*cVec.getY() - aVec.getX()*bVec.getZ()*cVec.getY() 
				- aVec.getY()*bVec.getX()*cVec.getZ() + aVec.getX()*bVec.getY()*cVec.getZ();
		
		if (det!=0.0) {
			//folded into the primitive unit cell
			double ka = 1/det*((-bVec.getZ()*cVec.getY() + bVec.getY()*cVec.getZ())*vx + (bVec.getZ()*cVec.getX() - 
				    bVec.getX()*cVec.getZ())*vy + (-bVec.getY()* cVec.getX() + bVec.getX()*cVec.getY())*vz);
			double kb = 1/det*((aVec.getZ()*cVec.getY() - aVec.getY()* cVec.getZ())*vx + (-aVec.getZ()*cVec.getX() + 
				    aVec.getX()*cVec.getZ())*vy + (aVec.getY()* cVec.getX() - aVec.getX()*cVec.getY())*vz);
			double kc = 1/det*((-aVec.getZ()*bVec.getY() + aVec.getY()* bVec.getZ())*vx + (aVec.getZ()*bVec.getX() - 
				    aVec.getX()*bVec.getZ())*vy + (-aVec.getY()* bVec.getX() + aVec.getX()* bVec.getY())*vz);
			
			ka -= Math.floor(ka);kb -= Math.floor(kb);kc -= Math.floor(kc);
			
			Point3D outFold = new Point3D(aVec.getX()* ka + bVec.getX()* kb + cVec.getX()* kc,
					aVec.getY()* ka + bVec.getY()* kb + cVec.getY()* kc,
					aVec.getZ()* ka + bVec.getZ()* kb + cVec.getZ()* kc);
			
			return outFold;
		}
		else return null;
	}
	private Cylinder makeCylinderConnect(Point3D origin, Point3D target, int thick) {
	    Point3D yAxis = new Point3D(0, 1, 0);
	    Point3D diff = target.subtract(origin);
	    double height = diff.magnitude();

	    Point3D mid = target.midpoint(origin);
	    Translate moveToMidpoint = new Translate(mid.getX(), mid.getY(), mid.getZ());

	    Point3D axisOfRotation = diff.crossProduct(yAxis);
	    double angle = Math.acos(diff.normalize().dotProduct(yAxis));
	    Rotate rotateAroundCenter = new Rotate(-Math.toDegrees(angle), axisOfRotation);

	    Cylinder cyl = new Cylinder(thick, height);

	    cyl.getTransforms().addAll(moveToMidpoint, rotateAroundCenter);

	    return cyl;
	}
	private GeoGroup makeTwoColorBond(Point3D origin, Point3D target, String colorOri, String colorTar) {
		//colorOri and colorTar are colors in hex form, e.g. "FF00FF"
		GeoGroup sm = new GeoGroup();
		Cylinder cy1 = makeCylinderConnect(origin, origin.midpoint(target), bondThick);
		Cylinder cy2 = makeCylinderConnect(origin.midpoint(target), target, bondThick);
		
		PhongMaterial mat1 = new PhongMaterial();
		mat1.setSpecularColor(Color.DARKGRAY);
		mat1.setDiffuseColor(Color.web(colorOri));
			 
		PhongMaterial mat2 = new PhongMaterial();
		mat2.setSpecularColor(Color.DARKGRAY);
		mat2.setDiffuseColor(Color.web(colorTar));
	       
		cy1.setMaterial(mat1);
		cy2.setMaterial(mat2);
		
		sm.getChildren().addAll(cy1,cy2);
		return sm;
	}
}
