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
import com.consts.Constants.EnumHybridFunc;
import com.consts.Constants.EnumHybridTreat;
import com.consts.Constants.EnumNumCondition;
import com.consts.Constants.EnumStep;
import agent.InputAgentScf;
import app.input.InputController;
import javafx.fxml.FXML;
import javafx.scene.control.Button;
import javafx.scene.control.CheckBox;
import javafx.scene.control.ComboBox;
import javafx.scene.control.Label;
import javafx.scene.control.TextField;
import javafx.scene.control.ToggleButton;
import javafx.scene.layout.VBox;
import main.MainClass;

public class InputScfHybridController extends InputController{

	@FXML
    private CheckBox checkResetAll;

    @FXML
    private Button infoResetAll;

    @FXML
    private Label applyLabel;

    @FXML
    private Button infoHybridType;

    @FXML
    private ComboBox<EnumHybridFunc> comboHybridType;

    @FXML
    private CheckBox checkHybridType;

    @FXML
    private Label applyLabel1;

    @FXML
    private Button infoTreat;

    @FXML
    private ComboBox<EnumHybridTreat> comboTreat;

    @FXML
    private CheckBox checkTreat;

    @FXML
    private ToggleButton toggleExtraGamma;

    @FXML
    private CheckBox checkExtraGamma;

    @FXML
    private Button infoExtraGamma;

    @FXML
    private TextField textEcut;

    @FXML
    private CheckBox checkEcut;

    @FXML
    private Button infoEcut;

    @FXML
    private Label applyLabel2;

    @FXML
    private Button infoNq;

    @FXML
    private CheckBox checkNq;

    @FXML
    private TextField textNq1,
    textNq2,
    textNq3;
    
    @FXML
    private Label statusInfo;
    
    @FXML
    private VBox vboxDetails;
    
	public InputScfHybridController(MainClass mc) {
		super(mc, EnumStep.SCF);
	}
	
	@Override
	public void initialize(URL location, ResourceBundle resources) {
		setPointerStatusTextField(statusInfo);//point all status messages to the Label statusInfo
		
		initParameterSet(comboHybridType, "enumHybrid", EnumHybridFunc.values(), 
				checkHybridType, infoHybridType, checkResetAll);
		
		comboHybridType.getSelectionModel().selectedItemProperty().addListener((observable, oldValue, newValue) ->
		{ 
			vboxDetails.setVisible(!EnumHybridFunc.defaultFunctional.equals(newValue));
			boolean isGauPbe = EnumHybridFunc.gaupbe.equals(newValue);
			checkTreat.setDisable(isGauPbe);comboTreat.setDisable(isGauPbe);
			if(checkTreat.isSelected()&&isGauPbe) {checkTreat.setSelected(false);}
			checkEcut.setDisable(isGauPbe);
			
			if(EnumHybridFunc.gaupbe.equals(oldValue) || isGauPbe) {checkEcut.setSelected(isGauPbe);}
			
			if(isGauPbe) {
				comboTreat.getSelectionModel().select(EnumHybridTreat.no);
			}
			else if(EnumHybridFunc.gaupbe.equals(oldValue)){//from gaupbe back, set to QE default
				comboTreat.getSelectionModel().select(EnumHybridTreat.gb);
			}
		});
		
		initParameterSet(comboTreat, "enumTreat", EnumHybridTreat.values(), 
				checkTreat, infoTreat, checkResetAll);
		initDoubleParameterSet(textEcut, "ecutvcut", EnumNumCondition.nonNegative, "", 
				checkEcut, infoEcut, checkResetAll);
		initParameterSet(toggleExtraGamma, "xgammaextrap", "on", "off", 
				checkExtraGamma, infoExtraGamma, checkResetAll);
		
		initIntegerParameterSet(textNq1, "nqx", EnumNumCondition.positive, "", checkNq, infoNq, checkResetAll);
		initIntegerParameterSet(textNq2, "nqy", EnumNumCondition.positive, "", checkNq, infoNq, checkResetAll);
		initIntegerParameterSet(textNq3, "nqz", EnumNumCondition.positive, "", checkNq, infoNq, checkResetAll);
		
		checkNq.selectedProperty().addListener((observable, oldValue, newValue) ->
		{ 
			if(newValue==null) {return;}
			if(newValue) {
				InputAgentScf iScf = (InputAgentScf) mainClass.projectManager.getStepAgent(EnumStep.SCF);
				if (iScf!=null) {
					//Currently this defaults to the size of the k-point mesh used.
					//In QE =< 5.0.2 it defaulted to nqx1=nqx2=nqx3=1.
					setField(textNq1, iScf.nkx);
					setField(textNq2, iScf.nky);
					setField(textNq3, iScf.nkz);
				}
			}
		});
		
		//checkResetAll
		checkResetAll.selectedProperty().addListener((observable, oldValue, newValue) ->
		{ 
			if(newValue!=null && !newValue.equals(allDefault)) {
				checkHybridType.setSelected(newValue);checkTreat.setSelected(newValue);
				checkEcut.setSelected(newValue);checkExtraGamma.setSelected(newValue);
				checkNq.setSelected(newValue);
				allDefault = newValue;
			}
		});
	}
	public void loadProjectParameters() {
		super.loadProjectParameters();
		InputAgentScf iScf = (InputAgentScf) mainClass.projectManager.getStepAgent(EnumStep.SCF);
		if (iScf!=null) {
			if(!iScf.nqx.isEnabled()) {setField(textNq1, iScf.nkx);}
			if(!iScf.nqy.isEnabled()) {setField(textNq2, iScf.nky);}
			if(!iScf.nqz.isEnabled()) {setField(textNq3, iScf.nkz);}
		}
	}

}
	






