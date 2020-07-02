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
import java.util.ResourceBundle;
import com.consts.Constants.EnumStep;
import javafx.beans.binding.Bindings;
import javafx.fxml.FXML;
import javafx.fxml.FXMLLoader;
import javafx.scene.control.Accordion;
import javafx.scene.control.ScrollPane;
import javafx.scene.control.TitledPane;
import javafx.scene.control.ComboBox;
import javafx.scene.control.Label;
import javafx.scene.layout.VBox;
import main.MainClass;
import app.input.geo.InputGeoAtomsController;
import app.input.geo.InputGeoCellController;
import app.input.geo.InputGeoElementsController;

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

    private VBox vboxAtoms,
    vboxCell,
    vboxElements;
    
    
    private InputGeoCellController contCell=null;
    
    private InputGeoAtomsController contAtom = null;
    
    private InputGeoElementsController contElem = null;
    
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
			comboGeo.getItems().add("1");
			comboGeo.getSelectionModel().select(0);
			comboGeo.getSelectionModel().selectedIndexProperty().addListener((ov, oldVal, newVal) -> {
				mainClass.projectManager.setCurrentGeoInd((int) newVal);
				loadProjectParameters();
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
				
			} catch (IOException e) {
				e.printStackTrace();
			}
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
		}
	}
    public void loadProjectParameters() {
    	if (contCell!=null) {
    		contCell.loadProjectParameters();}
    	if (contAtom!=null) {
    		contAtom.loadProjectParameters();}
    	if (contElem!=null) {
    		contElem.loadProjectParameters();}
	}
    public void setDisabled() {
    	labelGeoNote.setVisible(true);
    	titlePaneElements.setVisible(false);titlePaneCell.setVisible(false);titlePaneAtoms.setVisible(false);
    }
    public void setEnabled() {
    	labelGeoNote.setVisible(false);
    	titlePaneElements.setVisible(true);titlePaneCell.setVisible(true);titlePaneAtoms.setVisible(true);
    }
}
