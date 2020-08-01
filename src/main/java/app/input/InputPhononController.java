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
import com.consts.Constants.EnumStep;

import javafx.beans.binding.Bindings;
import javafx.fxml.FXML;
import javafx.scene.control.Button;
import javafx.scene.control.CheckBox;
import javafx.scene.control.ComboBox;
import javafx.scene.control.Label;
import javafx.scene.control.RadioButton;
import javafx.scene.control.TextField;
import javafx.scene.control.ToggleButton;
import javafx.scene.control.ToggleGroup;
import javafx.scene.layout.GridPane;
import javafx.scene.layout.VBox;
import main.MainClass;

public class InputPhononController extends InputK{
	
	@FXML
    private VBox vboxRoot,
    vboxK,
    vboxGammaQ;
	
	@FXML
    private GridPane gridRamanPara;

    @FXML
    private CheckBox checkResetAll;

    @FXML
    private Button infoResetAll;

    @FXML
    private TextField textConvThr;

    @FXML
    private CheckBox checkConvThr;

    @FXML
    private Button infoConvThr;

    @FXML
    private Button infoGamma;

    @FXML
    private RadioButton radioGrid;

    @FXML
    private RadioButton radioGamma;

    @FXML
    private VBox vboxNonGammaQ;

    @FXML
    private Button infoNqPh1;

    @FXML
    private TextField nqxPh;

    @FXML
    private TextField nqyPh;

    @FXML
    private TextField nqzPh;

    @FXML
    private CheckBox checkAsr;

    @FXML
    private Button infoAsr;

    @FXML
    private Label labelterations1;

    @FXML
    private ComboBox<?> comboAsr;

    @FXML
    private Button infoCalcType;

    @FXML
    private Label labelterations;

    @FXML
    private RadioButton radioDisp;

    @FXML
    private RadioButton radioDos;

    @FXML
    private TextField nqxMat;

    @FXML
    private TextField nqyMat;

    @FXML
    private TextField nqzMat;

    @FXML
    private Button infoNqMat;


    @FXML
    private CheckBox checkEpsil;

    @FXML
    private Button infoEpsil; 

    @FXML
    private TextField ramanRps;

    @FXML
    private TextField ramanNs;

    @FXML
    private TextField ramanDek;

    @FXML
    private CheckBox checkRamamPara;

    @FXML
    private Button infoRamanPara;

    @FXML
    private ToggleButton toggleEpsil;

    @FXML
    private Button infoRaman;

    @FXML
    private ToggleButton toggleRaman;

    @FXML
    private CheckBox checkRaman;

    @FXML
    private Label statusInfo,
    labelAsrMatdyn;
    
    @FXML
    private Button infoAsrMatdyn;

	public InputPhononController(MainClass mc) {
		super(mc, EnumStep.PH);
	}
	
	@Override
	public void initialize(URL location, ResourceBundle resources) {
		super.initialize(location, resources);
		super.disableUnit();
		
		radioGrid.selectedProperty().addListener((obs, oldVal, newVal) -> {
			this.radioGamma.setSelected(!newVal);
		    if(!newVal) {
		    	if(vboxRoot.getChildren().contains(vboxNonGammaQ)) {
		    		vboxRoot.getChildren().remove(vboxNonGammaQ);
		    	}
		    	if(!vboxRoot.getChildren().contains(vboxGammaQ)) {
		    		vboxRoot.getChildren().add(vboxGammaQ);
		    	}
		    }
		    else {
		    	if(vboxRoot.getChildren().contains(vboxGammaQ)) {
		    		vboxRoot.getChildren().remove(vboxGammaQ);
		    	}
		    	if(!vboxRoot.getChildren().contains(vboxNonGammaQ)) {
		    		vboxRoot.getChildren().add(vboxNonGammaQ);
		    	}
		    }
		}); 
		radioGamma.selectedProperty().addListener((obs, oldVal, newVal) -> {
			this.radioGrid.setSelected(!newVal);
		}); 
		//radioGamma.setSelected(true);
		
		initParameterSet(radioGrid, "ldisp", null, null, null, infoGamma, checkResetAll);
		initDoubleParameterSet(textConvThr, "tr2_ph", EnumNumCondition.positive, "", 
				checkConvThr, infoConvThr, checkResetAll);
		
		final ToggleGroup tgGroup2 = new ToggleGroup();
		radioDos.setToggleGroup(tgGroup2);radioDisp.setToggleGroup(tgGroup2);
		
		radioDos.selectedProperty().addListener((obs, oldVal, newVal) -> {
		    if(newVal) {
		    	vboxK.getChildren().clear();
		    }
		    else {
		    	setChild(vboxK);
		    }
		}); 
		
		radioDos.setSelected(true);
	}
	public void loadProjectParameters() {
		super.loadProjectParameters();

	}
}
	






