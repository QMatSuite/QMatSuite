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
import core.app.input.InputController;
import core.main.MainClass;
import javafx.fxml.FXML;
import javafx.scene.control.Button;
import javafx.scene.control.CheckBox;
import javafx.scene.control.ComboBox;
import javafx.scene.control.Label;
import javafx.scene.control.TextField;

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
		super(mc, EnumStep.NSCF);
	}
	
	@Override
	public void initialize(URL location, ResourceBundle resources) {
		setPointerStatusTextField(statusInfo);//point all status messages to the Label statusInfo
		
		//new
		initParameterSet(comboSmear, "enumSmearing", EnumSmearing.values(), true, checkSmear, infoSmear, checkResetAll);//true means not QE default
		initParameterSet(comboOccup, "enumOccupation", EnumOccupations.values(), true, checkOccup, infoOccup, checkResetAll);//true means not QE default
		comboOccup.getSelectionModel().selectedItemProperty().addListener((observable, oldValue, newValue) ->
		{ 
			if (newValue.equals(EnumOccupations.smearing)) {
				comboSmear.setDisable(false);checkSmear.setDisable(false);
				textSmearing.setDisable(false);
			}
			else {
				comboSmear.setDisable(true);checkSmear.setDisable(true);
				textSmearing.setDisable(true);
			}
		});
		setComboListener(unitSmearing, EnumUnitEnergy.values(), "enumEnergyUnit");

		
		checkGauss.setDisable(true);//no default for degauss
		setDoubleFieldListener(textSmearing, "degauss",EnumNumCondition.nonNegative);
		
		checknband.setSelected(true);
		
		checkKPoint.setDisable(true);//no default for kpoints
		setIntegerFieldListener(textKPoint1, "nkx",EnumNumCondition.positive);
		setIntegerFieldListener(textKPoint2, "nky",EnumNumCondition.positive);
		setIntegerFieldListener(textKPoint3, "nkz",EnumNumCondition.positive);
		
		initIntegerParameterSet(textnband, "nbnd", EnumNumCondition.positive, "Automated", checknband, infonband, checkResetAll);
		textnband.textProperty().addListener((observable, oldValue, newValue) -> {
			InputAgentNscf iNscf = (InputAgentNscf) mainClass.projectManager.getStepAgent(EnumStep.NSCF);
			if (iNscf==null) return;
			Integer tmp = str2int(newValue);
			if(tmp==null) {iNscf.nbnd.setEnabled(false);return;}
			else {if(tmp>0) {iNscf.nbnd.setEnabled(true);}}
		});
		
		//checkAll
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
		super.loadProjectParameters();

		InputAgentNscf iNscf = (InputAgentNscf) mainClass.projectManager.getStepAgent(EnumStep.NSCF);
		if (iNscf!=null) {
			setField(textSmearing, iNscf.degauss);
			setCombo(unitSmearing, iNscf.enumEnergyUnit);
			setField(textKPoint1, iNscf.nkx);
			setField(textKPoint2, iNscf.nky);
			setField(textKPoint3, iNscf.nkz);
		}
    }

}

