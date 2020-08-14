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
package app.centerwindow;

import java.net.URL;
import java.util.ResourceBundle;

import core.app.centerwindow.WorkScene3D;
import javafx.fxml.FXML;
import javafx.fxml.Initializable;
import javafx.scene.control.Button;
import javafx.scene.control.Label;
import javafx.scene.control.TextField;

public class Animate3DController implements Initializable{
	
	@FXML
    private Button buttonPrevious;

    @FXML
    private TextField textFieldStep;

    @FXML
    private Label labelTotalStep;

    @FXML
    private Button buttonNext;

    @FXML
    private Button buttonAutoPlay;

    @FXML
    private Label labelStatus;
    
	private WorkScene3D ws3d;
	
	private FileDataClass fileData;
	
	private int stepIndex = 0;
	
	public Animate3DController(WorkScene3D ws3dtmp, FileDataClass fd) {
		ws3d = ws3dtmp;
		fileData = fd;
	}
	@Override
	public void initialize(URL location, ResourceBundle resources) {
		setStatus("");
		stepIndex = 0;
		textFieldStep.setText(Integer.toString(stepIndex));
		buttonNext.setOnAction((event) -> {
			if(stepIndex<fileData.getTotalSteps()-1) {stepIndex++;updateAnimate3D();}
		});
		buttonPrevious.setOnAction((event) -> {
			if(stepIndex>0) {stepIndex--;updateAnimate3D();}
		});
	}
	public void setStatus(String st) {
		labelStatus.setText(st);
	}
	public void updateAnimate3D() {
		int maxStep = fileData.getTotalSteps();
		labelTotalStep.setText(Integer.toString(maxStep));
		
		if(stepIndex<0) {stepIndex=0;}
		else if(stepIndex>=maxStep) {stepIndex=maxStep-1;}
		
		textFieldStep.setText(Integer.toString(stepIndex+1));
		fileData.updateGeoAgent(stepIndex);
		ws3d.buildGeometry();
	}
}
