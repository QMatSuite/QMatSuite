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
import java.net.URL;
import java.util.ResourceBundle;

import com.consts.Constants.EnumCalc;
import com.consts.Constants.EnumOccupations;
import com.consts.Constants.EnumStep;

import agent.InputAgentScf;
import app.centerwindow.OutputViewerControllerQE;
import app.input.InputBandsController;
import app.input.InputBandsPPController;
import app.input.InputDosController;
import app.input.InputGeoControllerQE;
import app.input.InputMdController;
import app.input.InputNebController;
import app.input.InputNscfController;
import app.input.InputOptController;
import app.input.InputPdosController;
import app.input.InputPhononController;
import app.input.InputScfController;
import app.input.InputTddftController;
import app.menus.SettingsWindowController;
import core.app.JobDialogController;
import core.app.MainLeftPaneController;
import core.app.MainWindowController;
import core.app.input.InputGeoController;
import core.com.error.ShowAlert;
import core.main.MainClass;
import javafx.fxml.FXMLLoader;
import javafx.scene.control.MenuItem;
import javafx.scene.control.ScrollPane;
import javafx.scene.control.Tab;
import javafx.scene.control.Alert.AlertType;


public class MainWindowControllerQE extends MainWindowController{

	private ScrollPane scrollOpt,
	scrollScf,
	scrollDos,
	scrollNscf,
	scrollBands,
	scrollMd,
	scrollTddft,
	scrollBandsPP,
	scrollPhonon,
	scrollNeb,
	scrollPdos;
	
	private InputScfController contScf;
	
	private InputOptController contOpt;
	
	private InputNscfController contNscf;
	
	private InputDosController contDos;
	
	private InputMdController contMd;
	
	private InputTddftController contTddft;
	
	private InputPhononController contPhonon;
	
	private InputNebController contNeb;
	
	private InputBandsController contBands;
	
	private InputPdosController contPdos;
	
	private InputBandsPPController contBandsPP;
	
	public MainWindowControllerQE(MainClass mc) {
		super(mc);
	}
	@Override
	public void initialize(URL arg0, ResourceBundle arg1){
		super.initialize(arg0, arg1);
		try {
			contScf = new InputScfController(mainClass);
			FXMLLoader fxmlLoader = new FXMLLoader(getClass().getClassLoader().getResource("app/input/InputScf.fxml"));
			fxmlLoader.setController(contScf);
			scrollScf = fxmlLoader.load();
			//contScf.initialize();//must be later than the load
			
			contOpt = new InputOptController(mainClass);
			fxmlLoader = new FXMLLoader(getClass().getClassLoader().getResource("app/input/InputOpt.fxml"));
			fxmlLoader.setController(contOpt);
			scrollOpt = fxmlLoader.load();
			
			contMd = new InputMdController(mainClass);
			fxmlLoader = new FXMLLoader(getClass().getClassLoader().getResource("app/input/InputMd.fxml"));
			fxmlLoader.setController(contMd);
			scrollMd = fxmlLoader.load();
			
			contDos = new InputDosController(mainClass);
			fxmlLoader = new FXMLLoader(getClass().getClassLoader().getResource("app/input/InputDos.fxml"));
			fxmlLoader.setController(contDos);
			scrollDos = fxmlLoader.load();
			
			contPdos = new InputPdosController(mainClass,contDos);
			fxmlLoader = new FXMLLoader(getClass().getClassLoader().getResource("app/input/InputPDos.fxml"));
			fxmlLoader.setController(contPdos);
			scrollPdos = fxmlLoader.load();
			
			contNscf = new InputNscfController(mainClass);
			fxmlLoader = new FXMLLoader(getClass().getClassLoader().getResource("app/input/InputNscf.fxml"));
			fxmlLoader.setController(contNscf);
			scrollNscf = fxmlLoader.load();

			contBands= new InputBandsController(mainClass);
			fxmlLoader = new FXMLLoader(getClass().getClassLoader().getResource("app/input/InputBands.fxml"));
			fxmlLoader.setController(contBands);
			scrollBands = fxmlLoader.load();
			
			contBandsPP= new InputBandsPPController(mainClass);
			fxmlLoader = new FXMLLoader(getClass().getClassLoader().getResource("app/input/InputBandsPP.fxml"));
			fxmlLoader.setController(contBandsPP);
			scrollBandsPP = fxmlLoader.load();

			contTddft = new InputTddftController(mainClass);
			fxmlLoader = new FXMLLoader(getClass().getClassLoader().getResource("app/input/InputTddft.fxml"));
			fxmlLoader.setController(contTddft);
			scrollTddft = fxmlLoader.load(); 
			
			contPhonon = new InputPhononController(mainClass);
			fxmlLoader = new FXMLLoader(getClass().getClassLoader().getResource("app/input/InputPhonon.fxml"));
			fxmlLoader.setController(contPhonon);
			scrollPhonon = fxmlLoader.load(); 
			
			contNeb = new InputNebController(mainClass);
			fxmlLoader = new FXMLLoader(getClass().getClassLoader().getResource("app/input/InputNeb.fxml"));
			fxmlLoader.setController(contNeb);
			scrollNeb = fxmlLoader.load(); 
			
		} catch (IOException e) {
			// TODO Auto-generated catch block
			e.printStackTrace();
		}
		MenuItem calcScf = new MenuItem("Single energy");calcScf.setId("calcScf");
		MenuItem calcOpt = new MenuItem("Optimization");calcOpt.setId("calcOpt");
		MenuItem calcDos = new MenuItem("DOS");calcDos.setId("calcDos");
		MenuItem calcBands = new MenuItem("Bands");calcBands.setId("calcBands");
		MenuItem calcMd = new MenuItem("MD");calcMd.setId("calcMd");
		MenuItem calcTddft = new MenuItem("TDDFT");calcTddft.setId("calcTddft");
		MenuItem calcPhonon = new MenuItem("Phonon");calcPhonon.setId("calcPhonon");
		MenuItem calcNeb = new MenuItem("NEB");calcNeb.setId("calcNeb");
		MenuItem calcCustom = new MenuItem("Custom...");calcCustom.setId("calcCustom");
		contTree.calcMain.getItems().addAll(calcScf,calcOpt,calcDos,calcBands,calcMd,calcTddft,
				calcPhonon,calcNeb,calcCustom);
		calcScf.setOnAction((event) -> {
			openCalc(EnumCalc.SCF,true);
		});
		calcOpt.setOnAction((event) -> {
			openCalc(EnumCalc.OPT,true);
		});
		calcDos.setOnAction((event) -> {
			openCalc(EnumCalc.DOS,true);
		});
		calcBands.setOnAction((event) -> {
			openCalc(EnumCalc.BANDS,true);
		});
		calcMd.setOnAction((event) -> {
			openCalc(EnumCalc.BOMD,true);
		});
		calcTddft.setOnAction((event) -> {
			openCalc(EnumCalc.TDDFT,true);
		});
		calcPhonon.setOnAction((event) -> {
			openCalc(EnumCalc.PHONON,true);
		});
		calcNeb.setOnAction((event) -> {
			openCalc(EnumCalc.NEB,true);
		});
		calcCustom.setOnAction((event) -> {
			ShowAlert.showAlert(AlertType.INFORMATION, "Info", "Customized calculation not yet implemented.");
		});
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
			fxmlLoader = new FXMLLoader(getClass().getClassLoader().getResource("core/MainLeftPane.fxml"));
			fxmlLoader.setController(contTree);
			scrollLeft = fxmlLoader.load();scrollLeft.setId("mainScrollLeft");
			
			contSettings = new SettingsWindowController(mainClass);
			fxmlLoader = new FXMLLoader(getClass().getClassLoader().getResource("app/menus/settingsWindow.fxml"));
			fxmlLoader.setController(contSettings);
			borderSettings = fxmlLoader.load();
			
			contRun = new JobDialogController();
			fxmlLoader = new FXMLLoader(getClass().getClassLoader().getResource("core/JobDialog.fxml"));
			fxmlLoader.setController(contRun);
			borderRun = fxmlLoader.load();
			
			contOutput = new OutputViewerControllerQE(mainClass,contGeo);
			fxmlLoader = new FXMLLoader(getClass().getClassLoader().getResource("core/outputViewer.fxml"));
			fxmlLoader.setController(contOutput);
			splitOutput = fxmlLoader.load();
			
			
		} catch (IOException e) {
			// TODO Auto-generated catch block
			e.printStackTrace();
		}
		
	}
	@Override
	protected void openCalc(EnumCalc ec, boolean boolCreate) {
		
		
		//if(boolCreate), open a new calculation of type EnumCalc ec
		//if(!boolCreate), just load one existing calculation. MUST be entered through openCalc(String ecStr) in this case!
		if (ec==null) {return;}
		
		if (!mainClass.projectManager.existCurrentProject()) return;//abnormal!
		mainClass.projectManager.setGeoActive(false);
		
		EnumStep[] enumStepArray;
		
		switch(ec) {
		case SCF:
			enumStepArray = new EnumStep[] {EnumStep.SCF};
			addCalc(boolCreate, ec, enumStepArray);		
			break;
		case OPT:
			enumStepArray = new EnumStep[] {EnumStep.SCF,EnumStep.OPT};
			addCalc(boolCreate, ec, enumStepArray);
			break;
		case DOS:
			enumStepArray = new EnumStep[] {EnumStep.SCF,EnumStep.NSCF,EnumStep.DOS,EnumStep.PDOS};
			addCalc(boolCreate, ec, enumStepArray);
			break;
		case BANDS:
			enumStepArray = new EnumStep[] {EnumStep.SCF,EnumStep.BANDS,EnumStep.BANDSPP};
			addCalc(boolCreate, ec, enumStepArray);
			break;
		case BOMD:
			enumStepArray = new EnumStep[] {EnumStep.SCF,EnumStep.BOMD};
			addCalc(boolCreate, ec, enumStepArray);
			break;
		case TDDFT:
			enumStepArray = new EnumStep[] {EnumStep.SCF,EnumStep.TDDFT};
			addCalc(boolCreate, ec, enumStepArray);
			break;
		case PHONON:
			enumStepArray = new EnumStep[] {EnumStep.SCF,EnumStep.PH};//,EnumStep.Q2R,EnumStep.MATDYN
			addCalc(boolCreate, ec, enumStepArray);
			break;
		case NEB:
			enumStepArray = new EnumStep[] {EnumStep.SCF,EnumStep.NEB};
			addCalc(boolCreate, ec, enumStepArray);
			break;
		default:
			ShowAlert.showAlert(AlertType.INFORMATION, "Error", "Wrong calculation type!");
		}
		
		
	}
	protected void addCalc(boolean boolCreate, EnumCalc enumCalcThis, EnumStep[] enumStepArray) {
		//******inefficient here especially at the beginning of the program
		//******check by uncommenting the following code and see
//		String str = "\n";
//		for(EnumStep es:enumStepArray) {
//			str+=","+es.toString();
//		}
//		ShowAlert.showAlert(AlertType.INFORMATION, "Info", 
//				str);
		final int lengthArray = enumStepArray.length;
		if(lengthArray==0) return;
		String calcName;
		if(boolCreate) {
			//need to update current calculation before loading parameters
			mainClass.projectManager.addCalcToActiveProj(enumCalcThis); 
			calcName = mainClass.projectManager.getCurrentCalcName();
			//initialize controllers. This will be automatically done only once
			//***moved to the beginning of the program
			//update current status to trees
			contTree.updateCalcTree(calcName);
			
			//some calculation specific settings
			if(EnumCalc.TDDFT.equals(enumCalcThis)) {
				InputAgentScf iScf = (InputAgentScf) mainClass.projectManager.getStepAgent(EnumStep.SCF);
				if(iScf!=null) {
					iScf.boolKGamma.setValue(true);//only Gamma point calculation
					iScf.enumOccupation.setValue(EnumOccupations.fixed);//only fixed
				}
			}
		}
		
		//prepare to load GUI
		clearRightPane();
		//some calculation specific settings
		if(!EnumCalc.NEB.equals(enumCalcThis)) {
			addRightPane(scrollGeo,EnumStep.GEO);
			//load parameters for current project and calculation as well as update GUI
			contGeo.loadProjectParameters();
			((InputGeoController)contGeo).setDisabled();
		}
		
		for (int i=0;i<lengthArray;i++) {
			switch(enumStepArray[i]) {
				case SCF:contScf.loadProjectParameters();addRightPane(scrollScf,enumStepArray[i]);break;
				case OPT:contOpt.loadProjectParameters();addRightPane(scrollOpt,enumStepArray[i]);break;
				case BOMD:contMd.loadProjectParameters();addRightPane(scrollMd,enumStepArray[i]);break;
				case NSCF:contNscf.loadProjectParameters();addRightPane(scrollNscf,enumStepArray[i]);break;
				case DOS:contDos.loadProjectParameters();addRightPane(scrollDos,enumStepArray[i]);break;
				case PDOS:contPdos.loadProjectParameters();addRightPane(scrollPdos,enumStepArray[i]);break;
				case TDDFT:
					contTddft.loadProjectParameters();addRightPane(scrollTddft,enumStepArray[i]);
					break;
				case PH:
					contPhonon.loadProjectParameters();addRightPane(scrollPhonon,enumStepArray[i]);
					break;
				case BANDS:
					contBands.loadProjectParameters();addRightPane(scrollBands,enumStepArray[i]);
					break;
				case BANDSPP:
					contBandsPP.loadProjectParameters();addRightPane(scrollBandsPP,enumStepArray[i]);
					break;
				case NEB:
					contNeb.loadProjectParameters();addRightPane(scrollNeb,enumStepArray[i]);
					break;
				default:ShowAlert.showAlert(AlertType.INFORMATION, "Error", 
						"Nonimplemented controller: "+(enumStepArray[i]==null?"null":enumStepArray[i].toString()));break;
			}
		}

		//try {tabPaneRight.getSelectionModel().select(0);}catch (Exception e) {}//load second tab(not geo)
		try {tabPaneRight.getSelectionModel().select(0);}catch (Exception e) {}//load geo tab
		
		calcLabel.setText(enumCalcThis.getLong());
		
		//update center workscene
		
		Tab tabTmp = workSpaceTabPane.getSelectionModel().getSelectedItem();
		if(tabTmp!=null) {
			//((Tab) hboxOutput.getParent()).setContent(null);
			releaseHboxOutputContent();
			tabTmp.setContent(splitOutput);
			//ShowAlert.showAlert(AlertType.INFORMATION, "Debug", hboxOutput.toString());
		}
//		calcName = mainClass.projectManager.getCurrentCalcName();
//		if(calcName!=null) comboCalculation.getSelectionModel().select(calcName);
	}
}
