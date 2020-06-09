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

package app.input.scf;

import java.net.URL;
import java.util.ArrayList;
import java.util.ResourceBundle;
import com.consts.Constants.EnumStep;
import agent.InputAgentGeo;
import agent.InputAgentScf;
import app.input.InputController;
import app.input.geo.Element;
import javafx.beans.binding.Bindings;
import javafx.collections.FXCollections;
import javafx.collections.ObservableList;
import javafx.fxml.FXML;
import javafx.scene.control.Button;
import javafx.scene.control.CheckBox;
import javafx.scene.control.ComboBox;
import javafx.scene.control.Label;
import javafx.scene.control.TableCell;
import javafx.scene.control.TableColumn;
import javafx.scene.control.TableView;
import javafx.scene.control.TextField;
import javafx.scene.control.ToggleButton;
import javafx.scene.control.cell.PropertyValueFactory;
import javafx.scene.layout.HBox;
import main.MainClass;


public class InputScfHubbardController extends InputController{
	
	//InputScfHubbard
	
	@FXML private CheckBox checkResetAll,
	checkHubbardU;
	
	@FXML private Label statusLabel;//ok

	@FXML private ToggleButton applyToggle;//ok

	@FXML private Button applyInfo;
	
	@FXML private Button buttonAdd,
	buttonDel,
	buttonEdit;//ok

    @FXML private TableView<Element> elementTableHubbard;//ok
    
    @FXML private TableColumn<Element, Integer> indexColumnHubbard;//ok
    
    @FXML private TableColumn<Element, Double> hubbardColumn;//ok
    
    @FXML private TableColumn<Element, String> nameColumnHubbard;//ok
    
    @FXML private ComboBox<String> comboElements;//ok
    
    @FXML private TextField uValue;//ok
    
    @FXML private HBox hubbardHbox;//ok
    
    private Boolean initializedFlag=false;
    
    private ObservableList<Element> elemData;
    private boolean allDefault=false;
    
    public InputScfHubbardController(MainClass mc) {
    	super(mc);
    	elemData = FXCollections.observableArrayList();
	}
    @Override
	public void initialize(URL location, ResourceBundle resources) {
    	initialize();
    }
    public void initialize(){
    	applyToggle.setSelected(false);
    	applyToggle.setText("OFF");
    	hubbardHbox.setDisable(true);
    	elementTableHubbard.setDisable(true);
		applyToggle.selectedProperty().addListener((observable, oldValue, newValue) ->
		{ 
			InputAgentScf iScf = (InputAgentScf) mainClass.projectManager.getStepAgent(EnumStep.SCF);
			if (newValue) 
			{ 
				applyToggle.setText("ON");
				hubbardHbox.setDisable(false);
				elementTableHubbard.setDisable(false);
				if (iScf!=null)  iScf.lda_plus_u.setValue(true);
			}
			else 
			{ 
				applyToggle.setText("OFF"); 
				hubbardHbox.setDisable(true);
				elementTableHubbard.setDisable(true);
				if (iScf!=null)  iScf.lda_plus_u.setValue(false);
			}
		});
		initializedFlag = true;
		
		setupTable();

		buttonAdd.setOnAction((event) -> {	
			Element tmp = genElemFromInput();
    		if (tmp==null) return;
    		for (Element el:elemData) {
    			if(el.getAtomSpecies().toString().equals(tmp.getAtomSpecies().toString())) {
    				statusLabel.setText("The element alreay exists.");
    				return;
    			}
    		}
    		elemData.add(tmp);
    		InputAgentScf iGeo = (InputAgentScf) mainClass.projectManager.getStepAgent(EnumStep.SCF);
			if (iGeo!=null) {
				iGeo.elementList.add(tmp);
			}
			elementTableHubbard.getSelectionModel().selectLast();
		});
		buttonEdit.setOnAction((event) -> {	
    		int selec = elementTableHubbard.getSelectionModel().getSelectedIndex();
    		if (selec<0 || selec >= elemData.size()) {statusLabel.setText("Index out of bound to be editted.");return;}
    		statusLabel.setText("");
    		
    		Element tmp = genElemFromInput();
    		if (tmp==null) return;
    		for (int i = 0;i<elemData.size();i++) {
    			if (i==selec) continue;//not taken into account of the selected item
    			if(elemData.get(i).getAtomSpecies().toString().equals(tmp.getAtomSpecies().toString())) {
    				statusLabel.setText("The element alreay exists. Cannot edit to that one!");
    				return;
    			}
    		}
    		elemData.set(selec, tmp);
    		InputAgentScf iGeo = (InputAgentScf) mainClass.projectManager.getStepAgent(EnumStep.SCF);
			if (iGeo==null) {statusLabel.setText("Null input geo agent.");return;}
			iGeo.elementList.set(selec, tmp);
    		
			elementTableHubbard.getSelectionModel().select(selec);
		});
    	buttonDel.setOnAction((event) -> {	
    		int selec = elementTableHubbard.getSelectionModel().getSelectedIndex();
    		if (selec<0 || selec >= elemData.size()) {statusLabel.setText("No data is selected to be deleted.");return;}
    		statusLabel.setText("");
    		elemData.remove(selec);
    		InputAgentScf iGeo = (InputAgentScf) mainClass.projectManager.getStepAgent(EnumStep.SCF);
			if (iGeo!=null) {
				iGeo.elementList.remove(selec);
			}
			elementTableHubbard.getSelectionModel().selectNext();
		});
    	checkHubbardU.selectedProperty().addListener((observable, oldValue, newValue) ->
		{ 
			InputAgentScf iScf = (InputAgentScf) mainClass.projectManager.getStepAgent(EnumStep.SCF);
			if (iScf==null || newValue==null) return;
			if (newValue) {applyToggle.setSelected(iScf.lda_plus_u.resetDefault());applyToggle.setDisable(true);iScf.lda_plus_u.setEnabled(false);}//****not so efficient, double executing
			else {applyToggle.setDisable(false);iScf.lda_plus_u.setEnabled(true);if(checkResetAll.isSelected()) {allDefault=false;checkResetAll.setSelected(false);}}
		});
    	checkResetAll.selectedProperty().addListener((observable, oldValue, newValue) ->
		{ 
			if(newValue!=null && !newValue.equals(allDefault)) {//compare wrapper with primitive, != should be ok
				checkHubbardU.setSelected(newValue);
				allDefault = newValue;
			}
		});
	}
    private Element genElemFromInput() {
    	if(comboElements.getSelectionModel().getSelectedItem()==null) {statusLabel.setText("No element type selected.");return null;}
    	Double tmp;
    	try {
    		tmp = Double.valueOf(uValue.getText());
    	}catch(NumberFormatException e) {
    		statusLabel.setText("U must be a number");return null;
    	}
    	if (tmp<0) {statusLabel.setText("U cannot be negative.");return null;}
    	return new Element(comboElements.getSelectionModel().getSelectedItem(),tmp);
    }
    private void clearInput() {
    	statusLabel.setText("");
    	comboElements.getSelectionModel().clearSelection();
    	uValue.setText("");
    }
    private void setupTable() {
    	//ObservableList<Atom> atomsData =FXCollections.observableArrayList(new Atom("C",1),new Atom("H",2),new Atom("He",3));
    	indexColumnHubbard.setCellValueFactory(new PropertyValueFactory<Element, Integer>("index"));
    	indexColumnHubbard.setCellFactory(col -> {
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
    	nameColumnHubbard.setCellValueFactory(new PropertyValueFactory<Element, String>("atomSpecies"));
		hubbardColumn.setCellValueFactory(new PropertyValueFactory<Element, Double>("hubbardU"));
		
		elementTableHubbard.setItems(elemData);
		
		elementTableHubbard.getSelectionModel().selectedItemProperty().addListener((obs, oldSelect, newSelect) -> {
		    if (newSelect == null) {
		    	clearInput();
		    }
		    else {
		    	Element tmp = elementTableHubbard.getSelectionModel().getSelectedItem();
		    	comboElements.getSelectionModel().select(tmp.getAtomSpecies().toString());
		    	uValue.setText(tmp.getHubbardU().toString());
		    }
		});
    }
    public void loadProjectParameters() {
    	if (initializedFlag) {
    		InputAgentScf iScf = (InputAgentScf) mainClass.projectManager.getStepAgent(EnumStep.SCF);
			if (iScf!=null) {
	    		if (iScf.lda_plus_u.getValue()) {applyToggle.setText("ON");applyToggle.setSelected(true);hubbardHbox.setDisable(false);elementTableHubbard.setDisable(false);}
	    		else {applyToggle.setText("OFF");applyToggle.setSelected(false);hubbardHbox.setDisable(true);elementTableHubbard.setDisable(true);}
	    		elemData.clear();
	    		elemData.addAll(iScf.elementList);
			}
			
			InputAgentGeo iGeo = (InputAgentGeo) mainClass.projectManager.getCurrentGeoAgent();
			if (iGeo!=null) {
				ArrayList<String> elem = iGeo.getElementStringList();
				ObservableList<String> elem_obs = FXCollections.observableArrayList(elem);
				comboElements.setItems(elem_obs);
			}
    	}
	}
}
