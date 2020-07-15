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

package app.input;

import java.io.IOException;
import java.net.URL;
import java.util.ArrayList;
import java.util.ResourceBundle;
import com.consts.Constants.EnumStep;
import com.error.ShowAlert;
import javafx.beans.binding.Bindings;
import javafx.fxml.FXML;
import javafx.fxml.FXMLLoader;
import javafx.scene.Scene;
import javafx.scene.control.Accordion;
import javafx.scene.control.ScrollPane;
import javafx.scene.control.TitledPane;
import javafx.scene.control.Alert.AlertType;
import javafx.scene.control.Button;
import javafx.scene.control.ComboBox;
import javafx.scene.control.Label;
import javafx.scene.layout.BorderPane;
import javafx.scene.layout.VBox;
import javafx.stage.Modality;
import javafx.stage.Stage;
import javafx.stage.StageStyle;
import main.MainClass;
import app.input.geo.InputGeoAtomsController;
import app.input.geo.InputGeoCellController;
import app.input.geo.InputGeoElementsController;
import app.input.geo.PasteExternalWindowController;

public class InputGeoController extends InputController{
	
	@FXML private Accordion accordGeo;

	@FXML private ScrollPane cellPane,
	elementsPane,
	atomsPane;
	
	@FXML private Label labelGeoLeft,
	labelGeoRight;
	
	@FXML private ComboBox<String> comboGeo;
	
	@FXML private TitledPane titlePaneElements,
	titlePaneCell,
	titlePaneAtoms;
	
	@FXML private Label labelGeoNote;

	@FXML private Button buttonDeleteGeo,
	buttonDuplicateGeo,
	buttonPasteExternal;
	
    private VBox vboxAtoms,
    vboxCell,
    vboxElements;
    
    private InputGeoCellController contCell=null;
    
    private InputGeoAtomsController contAtom = null;
    
    private InputGeoElementsController contElem = null;
    
    private PasteExternalWindowController contPaste = null;
    
    private BorderPane borderPaste;
    
    public InputGeoController(MainClass mc) {
		super(mc, EnumStep.GEO);
	}

    @Override
   	public void initialize(URL location, ResourceBundle resources) {
    	initialize();
    }
    public void initialize() {
		// load sub panes, if not already loaded
		if (contCell==null) {
			setEnabled();
			comboGeo.getSelectionModel().selectedIndexProperty().addListener((ov, oldVal, newVal) -> {
				if((int) newVal != -1) {
					mainClass.projectManager.setCurrentGeoInd((int) newVal);
					loadProjectParameters();
				}
			});
			try {
				contCell = new InputGeoCellController(mainClass);
				FXMLLoader fxmlLoader1 = new FXMLLoader(getClass().getClassLoader().getResource("app/input/geo/InputGeoCell.fxml"));
				fxmlLoader1.setController(contCell);
				vboxCell = fxmlLoader1.load();
				
				contAtom = new InputGeoAtomsController(mainClass);
				FXMLLoader fxmlLoader2 = new FXMLLoader(getClass().getClassLoader().getResource("app/input/geo/InputGeoAtoms.fxml"));
				fxmlLoader2.setController(contAtom);
				vboxAtoms = fxmlLoader2.load();
				
				contElem = new InputGeoElementsController(mainClass);
				FXMLLoader fxmlLoader3 = new FXMLLoader(getClass().getClassLoader().getResource("app/input/geo/InputGeoElements.fxml"));
				fxmlLoader3.setController(contElem);
				vboxElements = fxmlLoader3.load();
				
				contPaste = new PasteExternalWindowController(mainClass);
				FXMLLoader fxmlLoader = new FXMLLoader(getClass().getClassLoader().getResource("app/input/geo/PasteExternalWindow.fxml"));
				fxmlLoader.setController(contPaste);
				borderPaste = fxmlLoader.load();
				
			} catch (IOException e) {
				e.printStackTrace();
			}
			
	    	//PasteExternalWindowController
	    	Scene scenePaste = new Scene(borderPaste);
	        Stage stagePaste = new Stage();
	        stagePaste.setTitle("Paste geometry from external");
	        stagePaste.initModality(Modality.APPLICATION_MODAL);
	        stagePaste.initStyle(StageStyle.DECORATED);
	        stagePaste.setScene(scenePaste);
	        
	    	buttonPasteExternal.setOnAction((event) -> {
	    		contPaste.initializeConversion();
	    		stagePaste.showAndWait();
	    		//after the input
	    		if(contPaste.isBoolSave()) {
	    			//ShowAlert.showAlert(AlertType.INFORMATION, "Debug", "Saved.");
	    			//****be careful here of references. In case of bug, use deepcopy
	    			//****investigate possible RAM leak here
	    			mainClass.projectManager.setCurrentGeoAgent(contPaste.getGeoAgent());
	    			this.loadProjectParameters();
	    		}
			});
	    	
			atomsPane.setContent(vboxAtoms);
			cellPane.setContent(vboxCell);
			elementsPane.setContent(vboxElements);
			contAtom.getAlat().textProperty().bind(Bindings.concat("alat: ",contCell.getAField().textProperty()));
			
			//when elementsPane expanded, automatically update the element table
			accordGeo.expandedPaneProperty().addListener((obs, oldSelect, newSelect) -> {
                if (titlePaneElements==newSelect && contElem!=null) {//here use == because check reference
                	contElem.loadProjectParameters();
                }
                if (contCell!=null) {contCell.updateCellA();}
	        });
			buttonDeleteGeo.setOnAction((event) -> {
				int ind = comboGeo.getSelectionModel().getSelectedIndex();
				mainClass.projectManager.removeGeoList(ind);
				loadGeoIndCombo();
			});
			buttonDuplicateGeo.setOnAction((event) -> {
				int ind = comboGeo.getSelectionModel().getSelectedIndex();
				mainClass.projectManager.duplicateGeoList(ind);
				loadGeoIndCombo();
			});
		}
	}
    public void loadGeoIndCombo() {
    	int sizeGeoList = mainClass.projectManager.getGeoListSize();
    	ArrayList<String> arrString = mainClass.projectManager.getGeoName();
		if(sizeGeoList<=0 || arrString==null) {
			ShowAlert.showAlert(AlertType.INFORMATION, "Error", "No item in geoList/geoName.");
			return;
		}
		if(sizeGeoList!=arrString.size()) {
			ShowAlert.showAlert(AlertType.INFORMATION, "Error", "Different size of geoList and geoName.");
			return;
		}
		if(comboGeo.getItems().size() != sizeGeoList) {
			comboGeo.getItems().clear();
			for(int i=0;i<sizeGeoList;i++) {
				comboGeo.getItems().add(Integer.toString(i+1)+"_"+arrString.get(i));
			}
		}
		Integer intTmp = mainClass.projectManager.getActiveGeoInd();
		if(intTmp==null || intTmp<0 || intTmp>=comboGeo.getItems().size()) {
			ShowAlert.showAlert(AlertType.INFORMATION, "Error", "active geometry index out of bound.");
			return;
		}
		comboGeo.getSelectionModel().select(intTmp);
    }
    public void loadProjectParameters() {
    	loadGeoIndCombo();
		
    	if (contCell!=null) {
    		contCell.loadProjectParameters();}
    	if (contAtom!=null) {
    		contAtom.loadProjectParameters();}
    	if (contElem!=null) {
    		contElem.loadProjectParameters();}
	}
    public void updatePseudoElementList() {
    	contElem.updatePseudoElementList();
    }
    public void setDisabled() {
    	labelGeoNote.setVisible(true);
    	titlePaneElements.setVisible(false);titlePaneCell.setVisible(false);titlePaneAtoms.setVisible(false);
    	buttonPasteExternal.setVisible(false);
    }
    public void setEnabled() {
    	labelGeoNote.setVisible(false);
    	titlePaneElements.setVisible(true);titlePaneCell.setVisible(true);titlePaneAtoms.setVisible(true);
    	buttonPasteExternal.setVisible(true);
    }
}
