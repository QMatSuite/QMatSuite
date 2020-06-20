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

import java.net.URL;
import java.util.ResourceBundle;

import com.consts.Constants.EnumNumCondition;
import com.consts.Constants.EnumOccupations;
import com.consts.Constants.EnumSmearing;
import com.consts.Constants.EnumStep;
import com.consts.Constants.EnumUnitEnergy;

import agent.InputAgentNscf;
import javafx.collections.FXCollections;
import javafx.collections.ObservableList;
import javafx.fxml.FXML;
import javafx.scene.control.Button;
import javafx.scene.control.CheckBox;
import javafx.scene.control.ComboBox;
import javafx.scene.control.Label;
import javafx.scene.control.TextField;
import main.MainClass;

public class InputNscfController extends InputController{

	@FXML
    private CheckBox checkResetAll;

    @FXML
    private Button infoResetAll;

    @FXML
    private Label kpointLabel;

    @FXML
    private Label occupLabel;

    @FXML
    private Label smearLabel;

    @FXML
    private Label smearWidthLabel;

    @FXML
    private TextField textKPoint1;

    @FXML
    private TextField textKPoint2;

    @FXML
    private TextField textKPoint3;

    @FXML
    private ComboBox<EnumOccupations> comboOccup;

    @FXML
    private ComboBox<EnumSmearing> comboSmear;

    @FXML
    private TextField textSmearing;

    @FXML
    private ComboBox<EnumUnitEnergy> unitSmearing;

    @FXML
    private Button infoKPoint;

    @FXML
    private Button infoOccup;

    @FXML
    private Button infoSmear;

    @FXML
    private Button infoSmearing;

    @FXML
    private CheckBox checkKPoint;

    @FXML
    private CheckBox checkOccup;

    @FXML
    private CheckBox checkSmear;

    @FXML
    private CheckBox checkGauss;

    @FXML
    private Button infonband;

    @FXML
    private CheckBox checknband;

    @FXML
    private TextField textnband;

    @FXML
    private Label nbandLabel,
    statusInfo;
    
	public InputNscfController(MainClass mc) {
		super(mc);
	}
	
	@Override
	public void initialize(URL location, ResourceBundle resources) {
		setPointerStatusTextField(statusInfo);//point all status messages to the Label statusInfo
		
		setIntegerFieldListener(textKPoint1, "nkx",EnumNumCondition.positive,EnumStep.NSCF);
		setIntegerFieldListener(textKPoint2, "nky",EnumNumCondition.positive,EnumStep.NSCF);
		setIntegerFieldListener(textKPoint3, "nkz",EnumNumCondition.positive,EnumStep.NSCF);
		
		//occupation list
		ObservableList<EnumOccupations> occup = 
    		    FXCollections.observableArrayList(EnumOccupations.values());
		comboOccup.setItems(occup);
		comboOccup.getSelectionModel().selectedItemProperty().addListener((observable, oldValue, newValue) ->
		{ 
			InputAgentNscf iNscf = (InputAgentNscf) mainClass.projectManager.getStepAgent(EnumStep.NSCF);
			if (iNscf!=null && newValue!=null) {
				iNscf.enumOccupation.setValue(newValue);
				if (newValue.equals(EnumOccupations.smearing)) {
					comboSmear.setDisable(false);checkSmear.setDisable(false);
					textSmearing.setDisable(false);
				}
				else {
					comboSmear.setDisable(true);checkSmear.setDisable(true);
					textSmearing.setDisable(true);
				}
			}
		});
		
		setComboListener(comboSmear, EnumSmearing.values(), "enumSmearing", EnumStep.NSCF);//smearing list
		
		setDoubleFieldListener(textSmearing, "degauss",EnumNumCondition.nonNegative,EnumStep.NSCF);
		setComboListener(unitSmearing, EnumUnitEnergy.values(), "enumEnergyUnit", EnumStep.NSCF);//ecutwfc
		
		setIntegerFieldListener(textnband, "nbnd",EnumNumCondition.positive,EnumStep.NSCF);
		
		textnband.textProperty().addListener((observable, oldValue, newValue) -> {
			InputAgentNscf iNscf = (InputAgentNscf) mainClass.projectManager.getStepAgent(EnumStep.NSCF);
			if (iNscf==null) return;
			Integer tmp = str2int(newValue);
			if(tmp==null) {
				statusInfo.setText("nbnd set to null!");
				iNscf.nbnd.setValue(null);
				iNscf.nbnd.setEnabled(false);return;
			}
			if (tmp!=null) {
				if(tmp<=0) {statusInfo.setText("Must be positive! Set to null.");iNscf.nbnd.setValue(null);return;}	
				statusInfo.setText("");
				iNscf.nbnd.setEnabled(true);
				iNscf.nbnd.setValue(tmp);
			}
		});
		
		//check boxes
		checkKPoint.setDisable(true);//no default for kpoints
		checkGauss.setDisable(true);//no default for degauss
		checknband.selectedProperty().addListener((observable, oldValue, newValue) ->
		{ 
			InputAgentNscf iNscf = (InputAgentNscf) mainClass.projectManager.getStepAgent(EnumStep.NSCF);
			if (iNscf==null || newValue==null) return;
			iNscf.nbnd.setEnabled(!newValue);
			textnband.setDisable(newValue);
			if(newValue) {
				textnband.setText("Automated");
			}
		});
		checknband.setSelected(true);
		
		resetComboBoxListener(checkOccup, comboOccup, "enumOccupation", EnumStep.NSCF, checkResetAll, true);//true means not QE default
		resetComboBoxListener(checkSmear, comboSmear, "enumSmearing", EnumStep.NSCF, checkResetAll, true);//true means not QE default
		checkGauss.setDisable(true);
		checkResetAll.selectedProperty().addListener((observable, oldValue, newValue) ->
		{ 
			if(newValue!=null && !newValue.equals(allDefault)) {
				allDefault = newValue;
				//checkKPoint.setSelected(newValue);
    			checkOccup.setSelected(newValue);
    			checkSmear.setSelected(newValue);
    			//checkGauss.setSelected(newValue);
    			checknband.setSelected(newValue);
			}
		});
	}
	
	public void loadProjectParameters() {
    	if (!comboOccup.getItems().isEmpty()) {
    		InputAgentNscf iNscf = (InputAgentNscf) mainClass.projectManager.getStepAgent(EnumStep.NSCF);
    		if (iNscf!=null) {
    			setCombo(comboOccup, iNscf.enumOccupation);
    			setCombo(unitSmearing, iNscf.enumEnergyUnit);
    			setCombo(comboSmear, iNscf.enumSmearing);
    			setField(textKPoint1, iNscf.nkx);
    			setField(textKPoint2, iNscf.nky);
    			setField(textKPoint3, iNscf.nkz);
    			setField(textSmearing, iNscf.degauss);
    			setField(textnband, iNscf.nbnd);
    			
    			//load default checkBoxes
    			checkKPoint.setSelected(!iNscf.nkx.isEnabled());//just for consistency, no use
    			checkOccup.setSelected(!iNscf.enumOccupation.isEnabled());
    			checkSmear.setSelected(!iNscf.enumSmearing.isEnabled());
    			checkGauss.setSelected(!iNscf.degauss.isEnabled());
    			checknband.setSelected(!iNscf.nbnd.isEnabled());
    		}
    	}
    }

}



