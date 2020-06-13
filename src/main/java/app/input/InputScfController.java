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

package main.java.app.input;

import java.io.IOException;
import java.lang.reflect.Field;
import java.net.URL;
import java.util.ResourceBundle;

import javafx.fxml.FXML;
import javafx.fxml.FXMLLoader;
import javafx.scene.control.Accordion;
import javafx.scene.control.Alert;
import javafx.scene.control.ScrollPane;
import javafx.scene.control.TitledPane;
import javafx.scene.control.Alert.AlertType;
import javafx.scene.control.Button;
import javafx.scene.control.CheckBox;
import javafx.scene.layout.AnchorPane;
import javafx.scene.layout.VBox;
import main.java.MainClass;
import main.java.agent.InputAgentScf;
import main.java.app.input.scf.InputScfHubbardController;
import main.java.app.input.scf.InputScfMagnetController;
import main.java.app.input.scf.InputScfStandardController;
import main.java.com.consts.Constants.EnumStep;

public class InputScfController extends InputController{

	@FXML private ScrollPane standardScroll;
	
	@FXML private Accordion accordion;
	
	@FXML private AnchorPane projectPane;
	
	@FXML private CheckBox checkSetProjectDefault;
	
	@FXML private Button buttonGetProjectDefault;
	
	@FXML private CheckBox setMag,
	setU,
	setHybrid,
	setVdw,
	setAdv,
	setE;
	
	@FXML private TitledPane standardPane;
	
	private TitledPane magnetPane,
	hubbardPane,
	hybridPane,
	vdwPane,
	efieldPane,
	advancedPane;

    private VBox vboxStandard,
    vboxHubbard,
    vboxMagnet,
    vboxHybrid,
    vboxVdw,
    vboxEfield,
    vboxAdvanced;
    
    private InputScfMagnetController contMagnet=null;
    
    private InputScfHubbardController contHubb=null;
    
    private InputScfStandardController contStandard=null;
    
    public InputScfController(MainClass mc) {
		super(mc);
	}
    
    @Override
	public void initialize(URL location, ResourceBundle resources) {
    	initialize();
    }
    public void initialize() {
    	// load sub panes if not already loaded
    	if (contMagnet==null){
			try {
				
				contStandard = new InputScfStandardController(mainClass);
				FXMLLoader fxmlLoader0 = new FXMLLoader(getClass().getClassLoader().getResource("app/input/scf/InputScfStandard.fxml"));
				fxmlLoader0.setController(contStandard);
				vboxStandard = fxmlLoader0.load();
				
				contMagnet = new InputScfMagnetController(mainClass);
				FXMLLoader fxmlLoader1 = new FXMLLoader(getClass().getClassLoader().getResource("app/input/scf/InputScfMagnet.fxml"));
				fxmlLoader1.setController(contMagnet);
				vboxMagnet = fxmlLoader1.load();
				
				contHubb = new InputScfHubbardController(mainClass);
				FXMLLoader fxmlLoader2 = new FXMLLoader(getClass().getClassLoader().getResource("app/input/scf/InputScfHubbard.fxml"));
				fxmlLoader2.setController(contHubb);
				vboxHubbard = fxmlLoader2.load();
				
				FXMLLoader fxmlLoader3 = new FXMLLoader(getClass().getClassLoader().getResource("app/input/scf/InputScfHybrid.fxml"));
				vboxHybrid = fxmlLoader3.load();
				
				FXMLLoader fxmlLoader4 = new FXMLLoader(getClass().getClassLoader().getResource("app/input/scf/InputScfVdw.fxml"));
				vboxVdw = fxmlLoader4.load();
				
				FXMLLoader fxmlLoader5 = new FXMLLoader(getClass().getClassLoader().getResource("app/input/scf/InputScfEfield.fxml"));
				vboxEfield = fxmlLoader5.load();
				
				FXMLLoader fxmlLoader6 = new FXMLLoader(getClass().getClassLoader().getResource("app/input/scf/InputScfAdvanced.fxml"));
				vboxAdvanced = fxmlLoader6.load();
				
				
			} catch (IOException e) {
				Alert alert1 = new Alert(AlertType.INFORMATION);
		    	alert1.setTitle("Error");
		    	alert1.setContentText("Cannot load .fxml file! "+e.getMessage());
		    	alert1.showAndWait();
				e.printStackTrace();
			}
			standardScroll.setContent(vboxStandard);
			magnetPane =  new TitledPane("Magnetization and SOC", vboxMagnet);magnetPane.setAnimated(false);
			hubbardPane = new TitledPane("DFT+U", vboxHubbard);hubbardPane.setAnimated(false);	
			hybridPane=  new TitledPane("Hybrid Functionals", vboxHybrid);hybridPane.setAnimated(false);
			vdwPane=  new TitledPane("Van der Waals", vboxVdw);vdwPane.setAnimated(false);
			efieldPane=  new TitledPane("Electric Field", vboxEfield);efieldPane.setAnimated(false);
			advancedPane=  new TitledPane("Advanced", vboxAdvanced);advancedPane.setAnimated(false);
			
			//accordion.getPanes().addAll(magnetPane,hubbardPane);
			
			setMag.setSelected(false);setU.setSelected(false);setHybrid.setSelected(false);
    		setVdw.setSelected(false);setAdv.setSelected(false);setE.setSelected(false);
    		setBoolFieldListener(setMag,"setMag",magnetPane);setBoolFieldListener(setU,"setU",hubbardPane);
    		setBoolFieldListener(setHybrid,"setHybrid",hybridPane);setBoolFieldListener(setVdw,"setVdw",vdwPane);
    		setBoolFieldListener(setAdv,"setAdv",advancedPane);setBoolFieldListener(setE,"setE",efieldPane);
    		
    		setExpandedListener(standardPane, "expandStandard");
    		setExpandedListener(magnetPane, "expandMag");
    		setExpandedListener(hubbardPane, "expandU");
    		setExpandedListener(hybridPane, "expandHybrid");
    		setExpandedListener(vdwPane, "expandVdw");
    		setExpandedListener(advancedPane, "expandAdv");
    		setExpandedListener(efieldPane, "expandE");
    		
    		checkSetProjectDefault.setSelected(false);
    		checkSetProjectDefault.selectedProperty().addListener((observable, oldValue, newValue) -> {
    			if(newValue) {
    				mainClass.projectManager.setStepAsDefault(EnumStep.SCF);
    			}
    		});
    		buttonGetProjectDefault.setOnAction((event) -> {
    			mainClass.projectManager.loadStepFromDefault(EnumStep.SCF);
    			loadProjectParameters();
    		});
    	}
	}
    public void loadProjectParameters() {
    	InputAgentScf ia = (InputAgentScf) mainClass.projectManager.getStepAgent(EnumStep.SCF);
		if (ia==null) return;
		setMag.setSelected(ia.setMag);setU.setSelected(ia.setU);setHybrid.setSelected(ia.setHybrid);
		setVdw.setSelected(ia.setVdw);setAdv.setSelected(ia.setAdv);setE.setSelected(ia.setE);//no need to set ia.setMag etc here
		
		//load expand property
		standardPane.setExpanded(ia.expandStandard);
		magnetPane.setExpanded(ia.expandMag);hubbardPane.setExpanded(ia.expandU);
		hybridPane.setExpanded(ia.expandHybrid);vdwPane.setExpanded(ia.expandVdw);
		advancedPane.setExpanded(ia.expandAdv);efieldPane.setExpanded(ia.expandE);
		
		if (contStandard!=null) contStandard.loadProjectParameters();
		if (contMagnet!=null) contMagnet.loadProjectParameters();
		if (contHubb!=null) contHubb.loadProjectParameters();
		
		if (mainClass.projectManager.isDefault()) {
			checkSetProjectDefault.setSelected(true);//********not efficient, will double set
		}
		else {
			checkSetProjectDefault.setSelected(false);
		}
	}
    private void setExpandedListener(TitledPane tp, String fieldName) {	
    	tp.expandedProperty().addListener((observable, oldValue, newValue) -> {
			//*********rethink later whether has risk of RAM leakage 
			InputAgentScf ia = (InputAgentScf) mainClass.projectManager.getStepAgent(EnumStep.SCF);
			if (ia==null) return;
			try {
				Field fd = InputAgentScf.class.getField(fieldName);
				fd.set(ia, newValue);
			} catch (Exception e) {
				Alert alert1 = new Alert(AlertType.INFORMATION);
		    	alert1.setTitle("Error");
		    	alert1.setContentText("Cannot set expand listener! "+e.getMessage());
		    	alert1.showAndWait();
				e.printStackTrace();
			}
		});
    }
    private void setBoolFieldListener(CheckBox tf, String fieldName, TitledPane tp) {	
		tf.selectedProperty().addListener((observable, oldValue, newValue) -> {
			//*********rethink later whether has risk of RAM leakage 
			if(newValue&&!accordion.getPanes().contains(tp)) accordion.getPanes().add(tp);
			if(!newValue&&accordion.getPanes().contains(tp)) accordion.getPanes().remove(tp);
			InputAgentScf ia = (InputAgentScf) mainClass.projectManager.getStepAgent(EnumStep.SCF);
			if (ia==null) return;
			try {
				Field fd = InputAgentScf.class.getField(fieldName);
				fd.set(ia, newValue);
			} catch (Exception e) {
				Alert alert1 = new Alert(AlertType.INFORMATION);
		    	alert1.setTitle("Error");
		    	alert1.setContentText("Cannot set listener! "+e.getMessage());
		    	alert1.showAndWait();
				e.printStackTrace();
			}
		});
    }

}
