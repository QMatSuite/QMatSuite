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
import java.util.ResourceBundle;

import com.consts.Constants.EnumStep;

import agent.InputAgentGeo;
import agent.InputAgentScf;
import app.input.geo.Atom;
import app.input.geo.Element;
import javafx.beans.binding.Bindings;
import javafx.collections.FXCollections;
import javafx.collections.ObservableList;
import javafx.fxml.FXML;
import javafx.fxml.Initializable;
import javafx.scene.control.Alert;
import javafx.scene.control.Button;
import javafx.scene.control.CheckBox;
import javafx.scene.control.ComboBox;
import javafx.scene.control.Label;
import javafx.scene.control.TableCell;
import javafx.scene.control.TableColumn;
import javafx.scene.control.TableView;
import javafx.scene.control.TextField;
import javafx.scene.control.ToggleButton;
import javafx.scene.control.Alert.AlertType;
import javafx.scene.control.cell.PropertyValueFactory;
import javafx.scene.layout.GridPane;
import main.MainClass;


public class InputScfMagnetController implements Initializable{
	
	//InputScfMagnet
	@FXML private CheckBox checkResetAll,
	checkPolariz,
	checkSoc;//ok
	
	@FXML private Label polarizLabel,
	spinorbitLabel,
	magmethodLabel,
	xmagLabel,
	ymagLabel,
	zmagLabel;
	
	@FXML private Label statusInfo,
	bottomStatusLabel;
	
	@FXML private ComboBox<String> polarizCombo;//ok
	
	@FXML private ToggleButton spinorbitToggle;//ok
	
	@FXML private Button polarizButton,
	spinorbitButton,
	fixmethodButton,
	xmagButton,
	ymagButton,
	zmagButton;//info, not implemented
	
	@FXML private TableView elementTable;
	
	@FXML private TableColumn<?, ?> indexColumn,
	nameColumn,
	magColumn,
	angle1Column,
	angle2Column;
	
	@FXML private CheckBox setForElements,
	setForAtoms;
	
	@FXML private Button editButton;//ok
	
	@FXML private Label labelNum,
	labelName,
	labelAngle1,
	labelAngle2;//ok
	
	@FXML private TextField textMag,
	textAngle1,
	textAngle2;//ok
	
	@FXML private GridPane grid1,
	grid2;
	
	private MainClass mainClass;
	
	private Boolean initializedFlag=false;
	
	private ObservableList<?> elemData;
	
	private boolean allDefault=false;
	
	public InputScfMagnetController(MainClass mc) {
		mainClass = mc;
		elemData = FXCollections.observableArrayList();
	}
    
    @Override
	public void initialize(URL location, ResourceBundle resources) {
    	initialize();
    }
    public void initialize(){
    	//spin polarized or not
    	if (polarizCombo.getItems().isEmpty()) {
    		//spin polarized setting
			ObservableList<String> polariz = 
	    		    FXCollections.observableArrayList("not spin-polarized","spin-polarized (collinear)","non collinear");
			polarizCombo.setItems(polariz);
			polarizCombo.setOnAction((event) -> {
				InputAgentScf ia = (InputAgentScf) mainClass.projectManager.getStepAgent(EnumStep.SCF);
				if (ia!=null) {
					setDisable();
					switch (polarizCombo.getValue()) {
						case "not spin-polarized": 
							ia.nspin.setValue(1);ia.noncolin.setValue(false);ia.noncolin.setEnabled(false);
							break;
						case "spin-polarized (collinear)":
							ia.nspin.setValue(2);ia.noncolin.setValue(false);ia.noncolin.setEnabled(false);
							break;
						case "non collinear":
							ia.nspin.setValue(null);ia.noncolin.setValue(true);ia.noncolin.setEnabled(true);
							break;
						default:
							Alert alert = new Alert(AlertType.INFORMATION);
					    	alert.setTitle("Error");
					    	alert.setContentText(polarizCombo.getValue()+" is invalid for polarization!");
					    	alert.showAndWait();
			    	}	    
				}
			});
			//initialize table
			indexColumn.setCellValueFactory(new PropertyValueFactory("index"));
	    	indexColumn.setCellFactory(col -> {
			    TableCell cell = new TableCell<>();
			    cell.textProperty().bind(Bindings.createStringBinding(() -> {
			        if (cell.isEmpty()) {
			            return null ;
			        } else {
			            return Integer.toString(cell.getIndex()+1);
			        }
			    }, cell.emptyProperty(), cell.indexProperty()));
			    return cell ;
			});
	    	nameColumn.setCellValueFactory(new PropertyValueFactory("atomSpecies"));
	    	magColumn.setCellValueFactory(new PropertyValueFactory("mag"));
	    	angle1Column.setCellValueFactory(new PropertyValueFactory("angle1"));
	    	angle2Column.setCellValueFactory(new PropertyValueFactory("angle2"));
	    	elementTable.getSelectionModel().selectedItemProperty().addListener((obs, oldSelect, newSelect) -> {
			    if (newSelect == null) {
			    	textMag.setText("");textAngle1.setText("");textAngle2.setText("");
			    }
			    else {
			    	if (setForElements.isSelected()) {
				    	Element tmp = (Element) newSelect;
				    	try{labelNum.setText(Integer.toString(elementTable.getSelectionModel().getSelectedIndex()+1));}catch(Exception e) {}
				    	labelName.setText(tmp.getAtomSpecies().toString());
				    	textMag.setText(tmp.getMag().toString());
				    	textAngle1.setText(tmp.getAngle1().toString());
				    	textAngle2.setText(tmp.getAngle2().toString());
			    	}
			    	else if(setForAtoms.isSelected()) {
			    		Atom tmp = (Atom) newSelect;
			    		try{labelNum.setText(Integer.toString(elementTable.getSelectionModel().getSelectedIndex()+1));}catch(Exception e) {}
				    	labelName.setText(tmp.getAtomSpecies().toString());
				    	textMag.setText(tmp.getMag().toString());
				    	textAngle1.setText(tmp.getAngle1().toString());
				    	textAngle2.setText(tmp.getAngle2().toString());
			    	}
			    }
			});
	    	//spin orbit toggle
			spinorbitToggle.setSelected(false);
			spinorbitToggle.setText("OFF");
			spinorbitToggle.selectedProperty().addListener((observable, oldValue, newValue) ->
			{ 
				InputAgentScf iScf = (InputAgentScf) mainClass.projectManager.getStepAgent(EnumStep.SCF);
				if (newValue) 
				{ 
					spinorbitToggle.setText("ON");
					statusInfo.setText("Notice: SOC is on, you must use full relativistic pseudopotential!");
					if (iScf!=null)  iScf.boolSoc.setValue(true);
				}
				else 
				{ 
					spinorbitToggle.setText("OFF"); 
					statusInfo.setText("");
					if (iScf!=null)  iScf.boolSoc.setValue(false);
				}
			});
			setForElements.selectedProperty().addListener((observable, oldValue, newValue) ->
			{
				InputAgentScf iScf = (InputAgentScf) mainClass.projectManager.getStepAgent(EnumStep.SCF);
				if (iScf!=null) iScf.setForElements.setValue(newValue);
				if (newValue&&setForAtoms.isSelected()) {setForAtoms.setSelected(false);}
				else {clearInput();updateTable();}//use else to avoid double updating
			});
			setForAtoms.selectedProperty().addListener((observable, oldValue, newValue) ->
			{
				InputAgentScf iScf = (InputAgentScf) mainClass.projectManager.getStepAgent(EnumStep.SCF);
				if (iScf!=null) iScf.setForAtoms.setValue(newValue);
				if (newValue&&setForElements.isSelected()) {setForElements.setSelected(false);}
				else {clearInput();updateTable();}//use else to avoid double updating
			});
			editButton.setOnAction((event) -> {	
	    		int selec = elementTable.getSelectionModel().getSelectedIndex();
	    		if (selec<0 || selec >= elemData.size()) {bottomStatusLabel.setText("No element/atom selected in the table.");return;}
	    		bottomStatusLabel.setText("");
	    		
	    		InputAgentGeo iGeo = (InputAgentGeo) mainClass.projectManager.getCurrentGeoAgent();
	    		if (iGeo==null) {bottomStatusLabel.setText("Null input geo agent.");return;}
	    		String st = polarizCombo.getSelectionModel().getSelectedItem();
	    		if (setForElements.isSelected()) {
	    			iGeo.elemListAll.get(selec).setMag(getMag(textMag));//null safe
	    			if (st!=null&&st.equals("non collinear")) {
		    			iGeo.elemListAll.get(selec).setAngle1(getAngle(textAngle1));//null safe
		    			iGeo.elemListAll.get(selec).setAngle2(getAngle(textAngle2));//null safe
	    			}
	    		}
	    		else if (setForAtoms.isSelected()) {
	    			iGeo.atomList.get(selec).setMag(getMag(textMag));//null safe
	    			if (st!=null&&st.equals("non collinear")) {
		    			iGeo.atomList.get(selec).setAngle1(getAngle(textAngle1));//null safe
		    			iGeo.atomList.get(selec).setAngle2(getAngle(textAngle2));//null safe
	    			}
	    		}
	    		else {return;}

				updateTable();
				elementTable.getSelectionModel().select(selec);
			});
			//reset 
			checkPolariz.selectedProperty().addListener((observable, oldValue, newValue) ->
    		{ 
    			InputAgentScf iScf = (InputAgentScf) mainClass.projectManager.getStepAgent(EnumStep.SCF);
				if (iScf==null || newValue==null) return;
				if (newValue) {polarizCombo.getSelectionModel().select(0);polarizCombo.setDisable(true);iScf.nspin.setEnabled(false);}
				else {polarizCombo.setDisable(false);iScf.nspin.setEnabled(true);if(checkResetAll.isSelected()) {allDefault=false;checkResetAll.setSelected(false);}}
			});
			checkSoc.selectedProperty().addListener((observable, oldValue, newValue) ->
    		{ 
    			InputAgentScf iScf = (InputAgentScf) mainClass.projectManager.getStepAgent(EnumStep.SCF);
				if (iScf==null || newValue==null) return;
				if (newValue) {spinorbitToggle.setSelected(iScf.resetboolSoc());spinorbitToggle.setDisable(true);iScf.boolSoc.setEnabled(false);}//****not so efficient, double executing
				else {spinorbitToggle.setDisable(false);iScf.boolSoc.setEnabled(true);if(checkResetAll.isSelected()) {allDefault=false;checkResetAll.setSelected(false);}}
			});
			checkResetAll.selectedProperty().addListener((observable, oldValue, newValue) ->
    		{ 
    			if(newValue!=null && !newValue.equals(allDefault)) {
    				checkPolariz.setSelected(newValue);checkSoc.setSelected(newValue);
    				allDefault = newValue;
    			}
			});
    	}
    	initializedFlag = true;
	}
    private void clearInput() {
    	labelNum.setText("");
    	labelName.setText("");
    	textMag.setText("");
    	textAngle1.setText("");
    	textAngle2.setText("");
    	bottomStatusLabel.setText("");
    	statusInfo.setText("");
    }
    private void setDisable() {
    	String st = polarizCombo.getSelectionModel().getSelectedItem();
    	if (st==null) return;
    	if("not spin-polarized".equals(st)) {
    		grid1.setDisable(true);
    		grid2.setDisable(true);
    		elementTable.setDisable(true);
    		angle1Column.setVisible(false);angle2Column.setVisible(false);
    		textAngle1.setVisible(false);textAngle2.setVisible(false);
    		labelAngle1.setVisible(false);labelAngle2.setVisible(false);
    	}
    	else if ("spin-polarized (collinear)".equals(st)) {
    		grid1.setDisable(false);
    		grid2.setDisable(false);//including textAngle1,textAngle2
    		//elementTable.setVisible(true);
    		elementTable.setDisable(false);
    		angle1Column.setVisible(false);angle2Column.setVisible(false);
    		textAngle1.setVisible(false);textAngle2.setVisible(false);
    		labelAngle1.setVisible(false);labelAngle2.setVisible(false);
    	}
    	else if ("non collinear".equals(st)) {
    		grid1.setDisable(false);
    		grid2.setDisable(false);
    		//elementTable.setVisible(true);
    		elementTable.setDisable(false);
    		angle1Column.setVisible(true);angle2Column.setVisible(true);
    		textAngle1.setVisible(true);textAngle2.setVisible(true);
    		labelAngle1.setVisible(true);labelAngle2.setVisible(true);
    	}
    	else {
    		Alert alert = new Alert(AlertType.INFORMATION);
        	alert.setTitle("Error!");
        	alert.setContentText("Selection of polarizCombo wrong.");
        	alert.showAndWait();
    	}
    }
    private Double getMag(TextField tf) {
    	if(tf==null) return null;
    	try {
    		Double tmp = Double.valueOf(tf.getText());
    		if(tmp < -1 || tmp > 1) {bottomStatusLabel.setText("Invalid mag input. Must be from -1 to 1!");return null;}
    		else {return tmp;}
    	}catch(Exception e) {
    		bottomStatusLabel.setText("Invalid mag input. Must be a number!");
    		return null;
    	}
    }
    private Double getAngle(TextField tf) {
    	if(tf==null) return null;
    	try {
    		Double tmp = Double.valueOf(tf.getText());
    		return tmp;
    	}catch(Exception e) {
    		bottomStatusLabel.setText("Invalid angle input. Must be a number!");
    		return null;
    	}
    }
    private void updateTable() {
    	InputAgentGeo iGeo = (InputAgentGeo) mainClass.projectManager.getCurrentGeoAgent();
		if (iGeo==null) return; 
		//iGeo.updateElemListAll();
		elemData.clear();
    	if (setForElements.isSelected()) {elemData = FXCollections.observableArrayList(iGeo.elemListAll);}
    	else if (setForAtoms.isSelected()) elemData = FXCollections.observableArrayList(iGeo.atomList);
    	else {return;}//nothing selected
    	
    	elementTable.setItems(elemData);
    }
    public void loadProjectParameters() {
    	if (initializedFlag) {
    		InputAgentScf iScf = (InputAgentScf) mainClass.projectManager.getStepAgent(EnumStep.SCF);
			if (iScf!=null) {
	        	if (iScf.noncolin.getValue() || iScf.nspin.getValue()==null) {
	    			polarizCombo.setValue("non collinear");
	    		}
	        	else if (iScf.nspin.getValue().equals(1)) {
	    			polarizCombo.setValue("not spin-polarized");
	    		}
	    		else if (iScf.nspin.getValue().equals(2)) {
	    			polarizCombo.setValue("spin-polarized (collinear)");
	    		}
	    		else {
	    			Alert alert = new Alert(AlertType.INFORMATION);
	            	alert.setTitle("Error");
	            	alert.setContentText("Wrong magnet! "+iScf.nspin.getValue()+"  "+iScf.noncolin.getValue());
	            	alert.showAndWait();
	    		}
	        	if (iScf.boolSoc.getValue()) {spinorbitToggle.setText("ON");spinorbitToggle.setSelected(true);}
	    		else {spinorbitToggle.setText("OFF");spinorbitToggle.setSelected(false);}
	        	
	        	setForElements.setSelected(iScf.setForElements.getValue());
	        	setForAtoms.setSelected(iScf.setForAtoms.getValue());
	        	clearInput();updateTable();//explicit updateTable, in case the setForElements and setForAtoms do not change
	        	setDisable();
			}
			
    	}
	}

}
