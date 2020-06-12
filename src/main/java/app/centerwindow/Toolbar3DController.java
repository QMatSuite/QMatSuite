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
package main.java.app.centerwindow;

import java.net.URL;
import java.util.ResourceBundle;

import javafx.beans.value.ChangeListener;
import javafx.beans.value.ObservableValue;
import javafx.fxml.FXML;
import javafx.fxml.Initializable;
import javafx.scene.control.Button;
import javafx.scene.control.CheckBox;
import javafx.scene.control.Label;
import javafx.scene.control.RadioButton;
import javafx.scene.control.Slider;
import javafx.scene.control.TextField;
import javafx.scene.control.Toggle;
import javafx.scene.control.ToggleButton;
import javafx.scene.control.ToggleGroup;
import javafx.scene.layout.VBox;

public class Toolbar3DController implements Initializable{
	@FXML private VBox rootVbox,
	functionVbox;
	@FXML private ToggleButton toggleShowToolbar;
	@FXML private Slider sliderBondScaling;
	@FXML private CheckBox checkFoldBack;
	@FXML private Label labelStatus;
	@FXML private TextField tfx;
	@FXML private TextField tfy;
	@FXML private TextField tfz;
	@FXML private Button btUpd,
	buttonResetView;
	@FXML private RadioButton radio1No,
	radio2Cryst,
	radio3Cart;
	
	private final ToggleGroup groupSupercell = new ToggleGroup();
	
	private WorkScene3D ws3d;
	
	public Toolbar3DController(WorkScene3D ws3dtmp) {
		ws3d = ws3dtmp;
	}
	@Override
	public void initialize(URL location, ResourceBundle resources) {
		sliderBondScaling.setMin(0.8);sliderBondScaling.setMax(1.2);
		sliderBondScaling.setValue(1.1);
		sliderBondScaling.setMajorTickUnit(0.1);
		//sliderBondScaling.setMinorTickCount(3);
		sliderBondScaling.setSnapToTicks(true);
		sliderBondScaling.setShowTickLabels(true);
		sliderBondScaling.valueProperty().addListener((obs, oldVal, newVal) -> {
		    if (newVal != null && newVal.doubleValue() > 0.0) {
		    	ws3d.bondScaling = newVal.doubleValue();
		    	ws3d.buildGeometry();//******not efficient!
		    }
		});
		checkFoldBack.setText("Fold atoms into cell");
		checkFoldBack.setSelected(false);ws3d.boolFoldBack=false;
		checkFoldBack.selectedProperty().addListener((obs, oldVal, newVal) -> {
		    if (newVal!=null) {
		    	ws3d.boolFoldBack=newVal;
		    	if (!checkFoldBack.isDisabled()) {
		    		ws3d.buildGeometry();//******not efficient!
		    		//labelStatus.setText("Updated through checkFoldBack.");
		    	}
		    }
		});
		toggleShowToolbar.setSelected(true);toggleShowToolbar.setText("Hide toolbar");
		toggleShowToolbar.selectedProperty().addListener((obs, oldVal, newVal) -> {
		    if (newVal) {
		    	toggleShowToolbar.setText("Hide toolbar");
		    	
		    	rootVbox.getChildren().add(functionVbox);
		    }
		    else {
		    	toggleShowToolbar.setText("Show toolbar");
		    	
		    	rootVbox.getChildren().remove(functionVbox);
		    }
		});
		//
		radio1No.setToggleGroup(groupSupercell);	
		radio2Cryst.setToggleGroup(groupSupercell);
		radio3Cart.setToggleGroup(groupSupercell);
		groupSupercell.selectedToggleProperty().addListener(new ChangeListener<Toggle>(){
		    public void changed(ObservableValue<? extends Toggle> ov, Toggle old_toggle, Toggle new_toggle) {
                if (new_toggle != null) {
                	//RadioButton bt = (RadioButton) groupSupercell.getSelectedToggle();
                	ws3d.supercellMode=groupSupercell.getToggles().indexOf(new_toggle);
                	//labelStatus.setText(ws3d.supercellMode.toString());
                	if(ws3d.supercellMode==1 || ws3d.supercellMode ==2) {//do supercell
                		checkFoldBack.setDisable(true);//first set disabled, so no update invoked
                		checkFoldBack.setSelected(true);
                		tfx.setDisable(false);tfy.setDisable(false);tfz.setDisable(false);btUpd.setDisable(false);
                	}
                	else {//no supercell
                		checkFoldBack.setDisable(false);
                		tfx.setDisable(true);tfy.setDisable(true);tfz.setDisable(true);btUpd.setDisable(true);
                		ws3d.buildGeometry();
                	}
                	//ws3d.buildGeometry();//******not efficient!May build twice!
                }                
            }
	    });
		radio1No.setSelected(true);
		//
		btUpd.setText("plot");
		btUpd.setOnAction((event) -> {
			try {
				Integer nx = Integer.valueOf(tfx.getText());
				Integer ny = Integer.valueOf(tfy.getText());
				Integer nz = Integer.valueOf(tfz.getText());
				if (nx<=0 || ny<=0 || nz<=0) {labelStatus.setText("Input must be positive!");return;}
				labelStatus.setText("");
				ws3d.nx = nx;ws3d.ny = ny;ws3d.nz = nz;
				ws3d.buildGeometry();
			}
			catch (NumberFormatException e) {
				labelStatus.setText("Please input integer!");
			}
		});
		buttonResetView.setOnAction((event) -> {
			ws3d.resetCamera();
		});
	}
	public void setStatus(String st) {
		labelStatus.setText(st);
	}
}
