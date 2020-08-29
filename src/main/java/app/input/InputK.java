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

import com.consts.Constants.EnumKUnitBands;
import com.consts.Constants.EnumStep;

import core.agent.InputAgentK;
import core.app.input.InputController;
import core.main.MainClass;
import javafx.fxml.FXMLLoader;
import javafx.scene.Node;
import javafx.scene.layout.VBox;

public abstract class InputK extends InputController{

    private Node nodeK;
    
    private InputKpointsController contK;

	public InputK(MainClass mc, EnumStep es) {
		super(mc, es);
	}
	
	@Override
	public void initialize(URL location, ResourceBundle resources) {
		try {
			contK = new InputKpointsController(mainClass, enumStep, this);
			FXMLLoader fxmlLoader = new FXMLLoader(getClass().getClassLoader().getResource("app/input/InputKpoints.fxml"));
			fxmlLoader.setController(contK);
			nodeK = fxmlLoader.load();
			
		} catch (IOException e) {
			e.printStackTrace();
		}
		
		setPointerStatusTextField(contK.statusTextField);
		
		setComboListener(contK.comboKPathUnit, EnumKUnitBands.values(), "enumKUnit");

	}
	public void disableUnit() {
		contK.comboKPathUnit.setDisable(true);
		contK.comboKPathUnit.getSelectionModel().select(EnumKUnitBands.crystal_b);//**********check here. Will try to invoke combolistener even when no agent
	}
	public void setChild(VBox vb) {
		vb.getChildren().clear();
		vb.getChildren().add(nodeK);
	}
	public void loadProjectParameters() {
		super.loadProjectParameters();
		
		contK.clearInput();
    	
		InputAgentK iK = (InputAgentK) mainClass.projectManager.getStepAgent(enumStep);
		if (iK==null) {contK.statusTextField.setText("Null input K agent.");return;}
    	setCombo(contK.comboKPathUnit, iK.enumKUnit);
    	
    	contK.kpointsData.clear();
    	contK.kpointsData.addAll(iK.listKPoints);
	}

}
	






