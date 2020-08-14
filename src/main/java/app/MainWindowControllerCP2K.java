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
package app;


import java.io.IOException;

import com.consts.Constants.EnumCalc;

import app.centerwindow.OutputViewerControllerCP2K;
import app.input.InputGeoControllerQE;
import app.menus.SettingsWindowController;
import core.app.JobDialogController;
import core.app.MainLeftPaneController;
import core.app.MainWindowController;
import core.main.MainClass;
import javafx.fxml.FXMLLoader;


public class MainWindowControllerCP2K extends MainWindowController{

	public MainWindowControllerCP2K(MainClass mc) {
		super(mc);
	}

	@Override
	protected void loadControllers() {
		// load all relevant panes and sub-panes
		try {		
			contGeo = new InputGeoControllerQE(mainClass);
			FXMLLoader fxmlLoader = new FXMLLoader(getClass().getClassLoader().getResource("app/input/InputGeo.fxml"));
			fxmlLoader.setController(contGeo);
			scrollGeo = fxmlLoader.load();
			//contGeo.initialize();//must be later than the load
			
			contTree = new MainLeftPaneController(mainClass);
			fxmlLoader = new FXMLLoader(getClass().getClassLoader().getResource("app/MainLeftPane.fxml"));
			fxmlLoader.setController(contTree);
			scrollLeft = fxmlLoader.load();scrollLeft.setId("mainScrollLeft");
			
			contSettings = new SettingsWindowController(mainClass);
			fxmlLoader = new FXMLLoader(getClass().getClassLoader().getResource("app/menus/settingsWindow.fxml"));
			fxmlLoader.setController(contSettings);
			borderSettings = fxmlLoader.load();
			
			contRun = new JobDialogController();
			fxmlLoader = new FXMLLoader(getClass().getClassLoader().getResource("app/JobDialog.fxml"));
			fxmlLoader.setController(contRun);
			borderRun = fxmlLoader.load();
			
			contOutput = new OutputViewerControllerCP2K(mainClass,contGeo);
			fxmlLoader = new FXMLLoader(getClass().getClassLoader().getResource("app/centerwindow/outputViewer.fxml"));
			fxmlLoader.setController(contOutput);
			splitOutput = fxmlLoader.load();
			
			
		} catch (IOException e) {
			// TODO Auto-generated catch block
			e.printStackTrace();
		}
		
	}

	@Override
	protected void openCalc(EnumCalc ec, boolean boolCreate) {
		// TODO Auto-generated method stub
		
	}
	
	

}
