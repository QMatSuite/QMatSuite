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

import java.lang.reflect.Field;
import java.net.URL;
import java.util.ResourceBundle;

import com.consts.BravaisLattice;
import com.consts.Constants.EnumNumCondition;
import com.consts.Constants.EnumUnitCellAngle;
import com.consts.Constants.EnumUnitCellLength;
import com.consts.Constants.EnumUnitCellParameter;

import agent.InputAgentGeo;
import agent.WrapperDouble;
import javafx.collections.FXCollections;
import javafx.collections.ObservableList;
import javafx.fxml.FXML;
import javafx.fxml.Initializable;
import javafx.scene.control.Alert;
import javafx.scene.control.Button;
import javafx.scene.control.CheckBox;
import javafx.scene.control.ComboBox;
import javafx.scene.control.Label;
import javafx.scene.control.TextField;
import javafx.scene.layout.GridPane;
import main.MainClass;
import javafx.scene.control.Alert.AlertType;

public class InputGeoCellController implements Initializable{

    @FXML private ComboBox<BravaisLattice> ibravCombo;//ok, String before, now enum. Better!

    @FXML private TextField aField,
    bField,
    cField,
    alphaField,
    betaField,
    gammaField;//ok. Use reflection: slow, but much shorter code

    @FXML private ComboBox<EnumUnitCellLength> aUnit;//ok
    
    @FXML private ComboBox<EnumUnitCellAngle> alphaUnit;//ok
    
    @FXML private Label bUnit,
    cUnit,
    betaUnit,
    gammaUnit;//ok

    @FXML private Button ibravInfo,
    aInfo,
    bInfo,
    cInfo,
    alphaInfo,
    betaInfo,
    gammaInfo,
    lattInfo;
    
    @FXML private CheckBox checkResetAll,
    ibravCheck,
    aCheck,
    bCheck,
    cCheck,
    alphaCheck,
    betaCheck,
    gammaCheck;

    @FXML private ComboBox<EnumUnitCellParameter> lattUnit;//ok
    
    @FXML private GridPane gridPaneLattice;//ok

    @FXML private Label statusInfo;//ok. Can add more
    
    @FXML private TextField aVecField1,
    aVecField2,
    aVecField3;//ok

    @FXML private TextField bVecField1,
    bVecField2,
    bVecField3;//ok

    @FXML private TextField cVecField1,
    cVecField2,
    cVecField3;//ok
	
	private MainClass mainClass;//nothing to be done here
	
	public InputGeoCellController(MainClass mc) {
		mainClass = mc;
	}
    
    @Override
	public void initialize(URL location, ResourceBundle resources) {
    	initialize();
    }
    private void setDisableInputFields() {
    	InputAgentGeo ia = (InputAgentGeo) mainClass.projectManager.getCurrentGeoAgent();
		if (ia==null) return;
		//if ibrav==null, all enabled
    	boolean a= false,
    			b= false,
    			c= false,
    			alpha = false,
    			beta= false,
    			gamma= false;
    	
    	ia.needAlatFromCell=true;
    	if(ia.ibrav.getValue()!=null) {
	    	switch(ia.ibrav.getValue()) {
				case 0:
					if (ia.unitCellParameter!=null && ia.unitCellParameter.equals(EnumUnitCellParameter.alat)) {
						ia.needAlatFromCell=true;a=(!ia.needCellA());b=true;c=true;alpha=true;beta=true;gamma=true;}
					else {ia.needAlatFromCell=false;a=(!ia.needCellA());b=true;c=true;alpha=true;beta=true;gamma=true;}
					break;
				case 1:a=false;b=true;c=true;alpha=true;beta=true;gamma=true;break;
				case 2:a=false;b=true;c=true;alpha=true;beta=true;gamma=true;break;
				case 3:a=false;b=true;c=true;alpha=true;beta=true;gamma=true;break;
				case 4:a=false;b=true;c=false;alpha=true;beta=true;gamma=true;break;
				case 5:a=false;b=true;c=true;alpha=true;beta=true;gamma=false;break;
				case 6:a=false;b=true;c=false;alpha=true;beta=true;gamma=true;break;
				case 7:a=false;b=true;c=false;alpha=true;beta=true;gamma=true;break;
				case 8:a=false;b=false;c=false;alpha=true;beta=true;gamma=true;break;
				case 9:a=false;b=false;c=false;alpha=true;beta=true;gamma=true;break;
				case 10:a=false;b=false;c=false;alpha=true;beta=true;gamma=true;break;
				case 11:a=false;b=false;c=false;alpha=true;beta=true;gamma=true;break;
				case 12:a=false;b=false;c=false;alpha=true;beta=true;gamma=false;break;
				case 13:a=false;b=false;c=false;alpha=true;beta=true;gamma=false;break;
				case 14:a=false;b=false;c=false;alpha=false;beta=false;gamma=false;break;
				default:
					Alert alert1 = new Alert(AlertType.INFORMATION);
			    	alert1.setTitle("Error");
			    	alert1.setContentText("Wrong ibrav!");
			    	alert1.showAndWait();
			    	return;
	    	}
    	}
    	aField.setDisable(a);ia.cellA.setEnabled(!a);
    	bField.setDisable(b);ia.cellB.setEnabled(!b);
    	cField.setDisable(c);ia.cellC.setEnabled(!c);
    	alphaField.setDisable(alpha);ia.cellAngleBC.setEnabled(!alpha);
    	betaField.setDisable(beta);ia.cellAngleAC.setEnabled(!beta);
    	gammaField.setDisable(gamma);ia.cellAngleAB.setEnabled(!gamma);
    	aUnit.setDisable(a&&b&&c);//set the unit to disable only when all inputs are disabled
    	alphaUnit.setDisable(alpha&&beta&&gamma);
    }
    public void initialize() {
    	checkResetAll.setDisable(true);ibravCheck.setDisable(true);aCheck.setDisable(true);bCheck.setDisable(true);
    	cCheck.setDisable(true);alphaCheck.setDisable(true);betaCheck.setDisable(true);gammaCheck.setDisable(true);
    	//ibrav
    	ObservableList<BravaisLattice> ibrav = FXCollections.observableArrayList(BravaisLattice.values());
    	ibravCombo.setItems(ibrav);
    	ibravCombo.setOnAction((event) -> {	
			if (ibravCombo.getValue()!=null) {
				InputAgentGeo ia = (InputAgentGeo) mainClass.projectManager.getCurrentGeoAgent();
				if (ia!=null) {
					ia.ibrav.setValue(ibravCombo.getValue().getInd());
					//if not (ibrav=0, free), disable gridPaneLattice
					gridPaneLattice.setDisable(!(ia.ibrav.equals(0)));
					setDisableInputFields();
					mainClass.projectManager.updateViewerPlot();
				}
			}
		});
    	//values, 
    	//**********not efficient because whenever parameters are loaded from InputAgentGeo, this will run again trying to write there
    	//the use of reflection increases code simplicity
    	//but may 1) result in error if the field name is not correct 2) much slower
    	setDoubleFieldListener(aField,"cellA",EnumNumCondition.positive);//for any case of ibrav, A cannot be zero
    	setDoubleFieldListener(bField,"cellB",EnumNumCondition.nonNegative);
    	setDoubleFieldListener(cField,"cellC",EnumNumCondition.nonNegative);
    	//**********do not delete the following comment. Alternative to reflection, faster but more tedious to write
//    	aField.textProperty().addListener((observable, oldValue, newValue) -> {
//    		InputAgentGeo ia = (InputAgentGeo) mainClass.projectManager.getCurrentGeoAgent();
//			if (ia!=null) {Double tmp = str2double(newValue);if (tmp!=null) ia.cellA=tmp;}});
//    	bField.textProperty().addListener((observable, oldValue, newValue) -> {
//    		InputAgentGeo ia = (InputAgentGeo) mainClass.projectManager.getCurrentGeoAgent();
//			if (ia!=null) {Double tmp = str2double(newValue);if (tmp!=null) ia.cellB=tmp;}});
//    	cField.textProperty().addListener((observable, oldValue, newValue) -> {
//    		InputAgentGeo ia = (InputAgentGeo) mainClass.projectManager.getCurrentGeoAgent();
//			if (ia!=null) {Double tmp = str2double(newValue);if (tmp!=null) ia.cellC=tmp;}});
    	setDoubleFieldListener(alphaField,"cellAngleBC",EnumNumCondition.no);
    	setDoubleFieldListener(betaField,"cellAngleAC",EnumNumCondition.no);
    	setDoubleFieldListener(gammaField,"cellAngleAB",EnumNumCondition.no);
    	setDoubleFieldListener(aVecField1,"vectorA1",EnumNumCondition.no);
    	setDoubleFieldListener(aVecField2,"vectorA2",EnumNumCondition.no);
    	setDoubleFieldListener(aVecField3,"vectorA3",EnumNumCondition.no);
    	setDoubleFieldListener(bVecField1,"vectorB1",EnumNumCondition.no);
    	setDoubleFieldListener(bVecField2,"vectorB2",EnumNumCondition.no);
    	setDoubleFieldListener(bVecField3,"vectorB3",EnumNumCondition.no);
    	setDoubleFieldListener(cVecField1,"vectorC1",EnumNumCondition.no);
    	setDoubleFieldListener(cVecField2,"vectorC2",EnumNumCondition.no);
    	setDoubleFieldListener(cVecField3,"vectorC3",EnumNumCondition.no);
    	//units,enumUnitCellLengthNames
    	aUnit.setItems(FXCollections.observableArrayList(EnumUnitCellLength.values()));
    	aUnit.getSelectionModel().selectedItemProperty().addListener( (options, oldValue, newValue) -> {
    		InputAgentGeo ia = (InputAgentGeo) mainClass.projectManager.getCurrentGeoAgent();
			if (ia!=null) {ia.unitCellLength=newValue;mainClass.projectManager.updateViewerPlot();}
        }); 
    	bUnit.textProperty().bind(aUnit.valueProperty().asString());
    	cUnit.textProperty().bind(aUnit.valueProperty().asString());
    	alphaUnit.setItems(FXCollections.observableArrayList(EnumUnitCellAngle.values()));
    	alphaUnit.getSelectionModel().selectedItemProperty().addListener( (options, oldValue, newValue) -> {
    		InputAgentGeo ia = (InputAgentGeo) mainClass.projectManager.getCurrentGeoAgent();
			if (ia!=null) {ia.unitCellAngle=newValue;mainClass.projectManager.updateViewerPlot();}
        }); 
    	betaUnit.textProperty().bind(alphaUnit.valueProperty().asString());
    	gammaUnit.textProperty().bind(alphaUnit.valueProperty().asString());
    	//lattUnit
    	ObservableList<EnumUnitCellParameter> latticeUn = FXCollections.observableArrayList(EnumUnitCellParameter.values());
    	lattUnit.setItems(latticeUn);
    	lattUnit.setOnAction((event) -> {
    		//*******only accessible when ibrav==0 -> this is not true when switching projects!!!???
			if (lattUnit.getValue()!=null) {
				InputAgentGeo ia = (InputAgentGeo) mainClass.projectManager.getCurrentGeoAgent();
				if (ia!=null) {
					EnumUnitCellParameter tmp = lattUnit.getValue();
					if(tmp!=null) ia.unitCellParameter=tmp;
					if (ia.ibrav.getValue()!=null && ia.ibrav.getValue().equals(0)) {
						if (lattUnit.getValue().equals(EnumUnitCellParameter.alat)) {
							ia.needAlatFromCell=true;aField.setDisable(!ia.needCellA());aUnit.setDisable(!ia.needCellA());
						}
						else {ia.needAlatFromCell=false;aField.setDisable(!ia.needCellA());aUnit.setDisable(!ia.needCellA());}
					}
					mainClass.projectManager.updateViewerPlot();
				}
				
			}
		});
	}
    private void setDoubleFieldListener(TextField tf, String fieldName,EnumNumCondition cond) {	
		tf.textProperty().addListener((observable, oldValue, newValue) -> {
			InputAgentGeo ia = (InputAgentGeo) mainClass.projectManager.getCurrentGeoAgent();
			if (ia==null) return;
			try {
				Field fd = InputAgentGeo.class.getField(fieldName);
				Double tmp = str2double(newValue);
				if (tmp!=null) {
					switch(cond) {
						case no:{break;}
						case positive:{if(tmp<=0) {statusInfo.setText("Must be positive!");return;} break;}
						case nonNegative:{if(tmp<0) {statusInfo.setText("Must not be negative!");return;} break;}
						default:
					}
					statusInfo.setText("");
					((WrapperDouble) fd.get(ia)).setValue(tmp);
					mainClass.projectManager.updateViewerPlot();
				}
			} catch (Exception e) {
				Alert alert1 = new Alert(AlertType.INFORMATION);
		    	alert1.setTitle("Error");
		    	alert1.setContentText("Cannot set listener! "+e.getMessage());
		    	alert1.showAndWait();
				e.printStackTrace();
			}
		});
    }
    public TextField getAField() {
    	return aField;
    }
    private Double str2double(String str) {
    	try {
    		statusInfo.setText("");
    		return Double.parseDouble(str);
    	}
    	catch(Exception e) {
    		statusInfo.setText("Error! Input is not double. "+e.getMessage());
    		return null;
    	}
    }
    public void loadProjectParameters() {
		InputAgentGeo ia = (InputAgentGeo) mainClass.projectManager.getCurrentGeoAgent();
		if (ia==null) return;
		BravaisLattice tmp = BravaisLattice.fromInd(ia.ibrav.getValue());//null compatible, contains situation where ia.ibrav==null
		setDisableInputFields();
		if (tmp==null) {ibravCombo.getSelectionModel().clearSelection();gridPaneLattice.setDisable(true);}
		else {ibravCombo.setValue(tmp);gridPaneLattice.setDisable(!(ia.ibrav.equals(0)));}
		aUnit.getSelectionModel().select(ia.unitCellLength);//null compatible
		alphaUnit.getSelectionModel().select(ia.unitCellAngle);//null compatible
		setField(aField,ia.cellA);setField(bField,ia.cellB);setField(cField,ia.cellC);
		setField(alphaField,ia.cellAngleBC);setField(betaField,ia.cellAngleAC);setField(gammaField,ia.cellAngleAB);
		if (ia.unitCellParameter==null) {lattUnit.getSelectionModel().clearSelection();}
		else {
			lattUnit.setValue(ia.unitCellParameter);
		}
		setField(aVecField1,ia.vectorA1);setField(aVecField2,ia.vectorA2);setField(aVecField3,ia.vectorA3);
		setField(bVecField1,ia.vectorB1);setField(bVecField2,ia.vectorB2);setField(bVecField3,ia.vectorB3);
		setField(cVecField1,ia.vectorC1);setField(cVecField2,ia.vectorC2);setField(cVecField3,ia.vectorC3);
		
		mainClass.projectManager.updateViewerPlot();//*****not so efficient
	}
    private void setField(TextField tf, WrapperDouble val) {
    	if(val.getValue()==null) tf.setText("");
    	else tf.setText(val.getValue().toString());
    }
    public void updateCellA(){
    	InputAgentGeo ia = (InputAgentGeo) mainClass.projectManager.getCurrentGeoAgent();
    	boolean a=(!ia.needCellA());
    	aField.setDisable(a);ia.cellA.setEnabled(!a);
    }
}
