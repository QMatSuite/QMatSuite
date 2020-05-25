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

package app.input.geo;

import java.net.URL;
import java.util.ResourceBundle;
import com.consts.Constants.EnumFunctional;
import com.consts.Constants.EnumPP;
import agent.InputAgentGeo;
import javafx.beans.binding.Bindings;
import javafx.collections.FXCollections;
import javafx.collections.ObservableList;
import javafx.fxml.FXML;
import javafx.fxml.Initializable;
import javafx.scene.control.Button;
import javafx.scene.control.CheckBox;
import javafx.scene.control.ComboBox;
import javafx.scene.control.Label;
import javafx.scene.control.TableCell;
import javafx.scene.control.TableColumn;
import javafx.scene.control.TableView;
import javafx.scene.control.cell.PropertyValueFactory;
import main.MainClass;

public class InputGeoElementsController implements Initializable{

	@FXML
    private Button defButton;

	@FXML private TableView<Element> elementTable;
    
    @FXML private TableColumn<Element, Integer> indexColumn;
    
    @FXML private TableColumn<Element, Double> massColumn;
    
    @FXML private TableColumn<Element, String> nameColumn;
    
    @FXML private TableColumn<Element, String> pseudoColumn;

    @FXML
    private Label ppTypePoint,xcFuncPoint,ecutwfcPoint,ecutrhoPoint;

    @FXML
    private Label ppTypeLabel,xcFuncLabel,ecutwfcLabel,ecutrhoLabel;

	
    @FXML private ComboBox<EnumFunctional> comboFunctional;
    
    @FXML private ComboBox<EnumPP> comboPP;
    
    @FXML private CheckBox checkRelativ;
    
    private MainClass mainClass;
    
    private ObservableList<Element> elemData;
	
	public InputGeoElementsController(MainClass mc) {
		mainClass = mc;
		elemData = FXCollections.observableArrayList();
	}
    
    @Override
    public void initialize(URL location, ResourceBundle resources) {
    	initialize();
    }
    public void initialize() {
    	//functional type
    	ObservableList<EnumFunctional> typeFunc = FXCollections.observableArrayList(EnumFunctional.values());
    	comboFunctional.setItems(typeFunc);
    	comboFunctional.setOnAction((event) -> {	
			if (comboFunctional.getValue()!=null) {
				InputAgentGeo ia = (InputAgentGeo) mainClass.projectManager.getCurrentGeoAgent();
				if (ia!=null) ia.typeFunctional=comboFunctional.getValue();
			}
		});
    	//pp type
    	ObservableList<EnumPP> typePP = FXCollections.observableArrayList(EnumPP.values());
    	comboPP.setItems(typePP);
    	comboPP.setOnAction((event) -> {	
			if (comboPP.getValue()!=null) {
				InputAgentGeo ia = (InputAgentGeo) mainClass.projectManager.getCurrentGeoAgent();
				if (ia!=null) ia.typePP=comboPP.getValue();
			}
		});
    	//full relativistic
    	checkRelativ.selectedProperty().addListener((obs, oldSelect, newSelect) -> {
    		InputAgentGeo ia = (InputAgentGeo) mainClass.projectManager.getCurrentGeoAgent();
			if (ia!=null) ia.isRelativ.setValue(newSelect);
		    if (newSelect) comboPP.getSelectionModel().select(EnumPP.USPP);//no need to change ia.typePP explicitly
		});
    	//setup element table
    	setupTable();
    }
    private void setupTable() {
    	indexColumn.setCellValueFactory(new PropertyValueFactory<Element, Integer>("index"));
    	indexColumn.setCellFactory(col -> {
		    TableCell<Element, Integer> cell = new TableCell<>();
		    cell.textProperty().bind(Bindings.createStringBinding(() -> {
		        if (cell.isEmpty()) {
		            return null ;
		        } else {
		            return Integer.toString(cell.getIndex()+1);
		        }
		    }, cell.emptyProperty(), cell.indexProperty()));
		    return cell ;
		});
    	nameColumn.setCellValueFactory(new PropertyValueFactory<Element, String>("atomSpecies"));
    	massColumn.setCellValueFactory(new PropertyValueFactory<Element, Double>("atomMass"));
    	pseudoColumn.setCellValueFactory(new PropertyValueFactory<Element, String>("pseudoPotFile"));
    	
    	elementTable.setItems(elemData);
		
    	elementTable.getSelectionModel().selectedItemProperty().addListener((obs, oldSelect, newSelect) -> {
		    //to be added
		});
    }
    public void loadProjectParameters() {
    	InputAgentGeo iGeo = (InputAgentGeo) mainClass.projectManager.getCurrentGeoAgent();
		if (iGeo==null) return;
		//iGeo.updateElemListAll();//from atom generate elements table
		if (iGeo.typeFunctional==null) {comboFunctional.getSelectionModel().clearSelection();}
		else {comboFunctional.getSelectionModel().select(iGeo.typeFunctional);}
		if (iGeo.typePP==null) {comboPP.getSelectionModel().clearSelection();}
		else {comboPP.getSelectionModel().select(iGeo.typePP);}
		checkRelativ.setSelected(iGeo.isRelativ.getValue());//should not be null!
		elemData.clear();
		elemData.addAll(iGeo.elemListAll);
    }
}
