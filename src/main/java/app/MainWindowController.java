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


import java.io.File;
import java.io.IOException;
import java.net.URL;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.Optional;
import java.util.ResourceBundle;
import javafx.application.Platform;
import javafx.fxml.FXML;
import javafx.fxml.FXMLLoader;
import javafx.fxml.Initializable;
import javafx.geometry.Insets;
import javafx.scene.Group;
import javafx.scene.Node;
import javafx.scene.Scene;
import javafx.scene.control.Alert;
import javafx.scene.control.Alert.AlertType;
import javafx.scene.control.Button;
import javafx.scene.control.ComboBox;
import javafx.scene.control.Label;
import javafx.scene.control.Menu;
import javafx.scene.control.MenuButton;
import javafx.scene.control.MenuItem;
import javafx.scene.control.RadioButton;
import javafx.scene.control.ScrollPane;
import javafx.scene.control.Tab;
import javafx.scene.control.TabPane;
import javafx.scene.control.TabPane.TabClosingPolicy;
import javafx.scene.control.TextInputDialog;
import javafx.scene.control.ToggleGroup;
import javafx.scene.layout.Background;
import javafx.scene.layout.BackgroundFill;
import javafx.scene.layout.BorderPane;
import javafx.scene.layout.CornerRadii;
import javafx.scene.layout.HBox;
import javafx.scene.layout.Pane;
import javafx.scene.layout.VBox;
import javafx.stage.DirectoryChooser;
import javafx.stage.Modality;
import javafx.stage.Stage;
import javafx.stage.StageStyle;
import main.MainClass;
import app.centerwindow.WorkTabContent;
import app.input.InputBandsController;
import app.input.InputDosController;
import app.input.InputGeoController;
import app.input.InputMdController;
import app.input.InputNscfController;
import app.input.InputOptController;
import app.input.InputScfController;
import app.input.InputTddftController;
import app.menus.SettingsWindowController;
import com.consts.Constants.EnumCalc;
import com.consts.Constants.EnumStep;
import com.error.ErrorMsg;
import com.error.ShowAlert;
import com.programconst.Coloring;
import com.programconst.DefaultFileNames.SettingKeys;
import input.ContainerInputString;
import job.JobNode;

public class MainWindowController implements Initializable{
	
	@FXML private BorderPane basePane;
	
    @FXML private Menu menuFile;
    
    @FXML private MenuButton calcMain;
    
    @FXML private MenuItem calcScf,
    calcOpt,
    calcDos,
    calcBands,
    calcMd,
    calcTddft,
    calcCustom,
    menuAbout,
    menuSaveProjectAs,
    menuLoadProject;
    
    @FXML private MenuItem stopCurrentJob,
    stopAllJobs,
    settingsMenuItem;
    
    @FXML private Button createProject,
    showInputButton,
    runJob,
    buttonOpenWorkSpace,
    saveProjectButton;
    
    @FXML private Label textWorkSpace;
    
    @FXML private Pane paneWorkSpace;
    
    @FXML private ComboBox<String> comboProject,
    comboCalculation;
    
	@FXML private ScrollPane inputField;
	
	@FXML private HBox hboxRight,
	hboxLeft;
	
	@FXML private Label calcLabel,
	currentJobLabel;
	
	@FXML private TabPane workSpaceTabPane;
	
	@FXML private RadioButton radioGeometry, 
	radioCalculation;
	
	@FXML private BorderPane rootPane;
	
	private ScrollPane scrollGeo,
	scrollOpt,
	scrollScf,
	scrollDos,
	scrollNscf,
	scrollBands,
	scrollMd,
	scrollTddft;
	
	private ScrollPane scrollLeft;
	
	private BorderPane borderSettings;
	
	private TabPane tabPaneRight;
	
	private Boolean tabPaneStatusRight,
	scrollStatusLeft;
	
	private MainClass mainClass;
	
	private InputScfController contScf;
	
	private InputGeoController contGeo;
	
	private InputOptController contOpt;
	
	private InputNscfController contNscf;
	
	private InputDosController contDos;
	
	private InputMdController contMd;
	
	private InputTddftController contTddft;
			
	private MainLeftPaneController contTree;
	
	private InputBandsController contBands;
	
	private SettingsWindowController contSettings;
	
	private HashMap<String, Tab> projectTabDict;
	
	private final ToggleGroup tgGroup = new ToggleGroup();
	
	private Thread thread1;
	
	
	
	private WorkTabContent workTabContent;
			
	public MainWindowController(MainClass mc) {
		mainClass = mc;
	}
	
	@Override
	public void initialize(URL arg0, ResourceBundle arg1){
		workSpaceTabPane.setTabClosingPolicy(TabClosingPolicy.SELECTED_TAB);

		
		projectTabDict = new HashMap<String, Tab>();
		
		//set the style of workspace and QEEngine fields
		textWorkSpace.setBackground(new Background(new BackgroundFill(Coloring.defaultFile, 
				CornerRadii.EMPTY, Insets.EMPTY)));
		textWorkSpace.prefWidthProperty().bind(paneWorkSpace.widthProperty());
		textWorkSpace.prefHeightProperty().bind(paneWorkSpace.heightProperty());

		
		tabPaneRight = null;
		tabPaneStatusRight = false;
		
		
		
		// load all relevant panes and sub-panes
		try {
			contScf = new InputScfController(mainClass);
			FXMLLoader fxmlLoader = new FXMLLoader(getClass().getClassLoader().getResource("app/input/InputScf.fxml"));
			fxmlLoader.setController(contScf);
			scrollScf = fxmlLoader.load();
			//contScf.initialize();//must be later than the load
			
			contGeo = new InputGeoController(mainClass);
			fxmlLoader = new FXMLLoader(getClass().getClassLoader().getResource("app/input/InputGeo.fxml"));
			fxmlLoader.setController(contGeo);
			scrollGeo = fxmlLoader.load();
			//contGeo.initialize();//must be later than the load
			
			
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
			
			contNscf = new InputNscfController(mainClass);
			fxmlLoader = new FXMLLoader(getClass().getClassLoader().getResource("app/input/InputNscf.fxml"));
			fxmlLoader.setController(contNscf);
			scrollNscf = fxmlLoader.load();

			contBands= new InputBandsController(mainClass);
			fxmlLoader = new FXMLLoader(getClass().getClassLoader().getResource("app/input/InputBands.fxml"));
			fxmlLoader.setController(contBands);
			scrollBands = fxmlLoader.load();

			contTddft = new InputTddftController(mainClass);
			fxmlLoader = new FXMLLoader(getClass().getClassLoader().getResource("app/input/InputTddft.fxml"));
			fxmlLoader.setController(contTddft);
			scrollTddft = fxmlLoader.load(); 
			
			contTree = new MainLeftPaneController(mainClass);
			fxmlLoader = new FXMLLoader(getClass().getClassLoader().getResource("app/MainLeftPane.fxml"));
			fxmlLoader.setController(contTree);
			scrollLeft = fxmlLoader.load();scrollLeft.setId("mainScrollLeft");
			
			contSettings = new SettingsWindowController(mainClass);
			fxmlLoader = new FXMLLoader(getClass().getClassLoader().getResource("app/menus/settingsWindow.fxml"));
			fxmlLoader.setController(contSettings);
			borderSettings = fxmlLoader.load();
			
			
		} catch (IOException e) {
			// TODO Auto-generated catch block
			e.printStackTrace();
		}
		
		workTabContent =  new WorkTabContent(mainClass,workSpaceTabPane,projectTabDict,contGeo);
		
		contTree.buttonOpenSelected.setOnAction((event) -> {
			String projName = contTree.getSelectedProject();
			if(projName==null || projName.isEmpty()) return;
			
			File wsDir = mainClass.projectManager.getWorkSpaceDir();
			
			if(wsDir==null || !wsDir.canRead()) {return;}
			
			String msg = mainClass.projectManager.loadProject(wsDir, projName);
			
			if(msg!=null) {
				if(msg.contains(ErrorMsg.alreadyContainsProject)) {
					ShowAlert.showAlert(AlertType.INFORMATION, "Error", msg);
			    	return;
		    	}
						
				if(msg.contains(ErrorMsg.cannotFindProjectFolder)) {
					contTree.updateProjects(true);
					ShowAlert.showAlert(AlertType.INFORMATION, "Error", msg);
					return;}
			}
			createProjectGui(projName);//loading GUI
			
			contTree.setOpenCloseButtons(false);
			
			if(msg!=null) {
				ShowAlert.showAlert(AlertType.INFORMATION, "Info", msg);
			}
		});
		contTree.buttonCloseSelected.setOnAction((event) -> {
			String projName = contTree.getSelectedProject();
			closeProject(projName);//should be null safe and empty safe
		});
		
		radioGeometry.setText("Geometry");
		radioGeometry.setToggleGroup(tgGroup);
		radioGeometry.setSelected(true);
		radioCalculation.setText("Calculation");
		radioCalculation.setToggleGroup(tgGroup);
		tgGroup.selectedToggleProperty().addListener((ov, old_toggle, new_toggle) -> {
			toggleGeometry();
		});
		
		setProjectNull();
		
		initializeLeftRightPane();//initialize tabPaneRight
		
		loadEnvironmentPaths();
		
		createProject.setOnAction((event) -> {
			
			String projName = null;
			String msg = null;
			
			File wsDir = mainClass.projectManager.getWorkSpaceDir();
			if(wsDir==null) return;
			
			File projDir=null;
			
			if(mainClass.isTestMode()) {
				int projectAllCount = mainClass.projectManager.getProjectNumber();
				do {
					projName = "testProject"+Integer.toString(projectAllCount);
					msg = mainClass.projectManager.checkProjectName(projName);
					projDir = new File(wsDir,projName);
					if(projDir.exists()) {msg="Project exists in the workspace folder!";}
					projectAllCount++;
				} while (msg!=null);
			}
			else {
				TextInputDialog promptProjName = new TextInputDialog(); 
				
				promptProjName.setHeaderText("Enter the project name");
				do {
					Optional<String> result = promptProjName.showAndWait();
					if (result.isPresent()) {
						projName = promptProjName.getEditor().getText();
						msg = mainClass.projectManager.checkProjectName(projName);
						promptProjName.setHeaderText(msg);
					}else {
						return;
					}
				} while (msg!=null);
			}
			
			
			
			projDir = new File(wsDir,projName);
			
			if (projDir.exists()) {
				ShowAlert.showAlert(AlertType.INFORMATION, "Error", "Project with the same name already existed in the workspace. Please try another name.");
				return;
			}
			
			msg = mainClass.projectManager.addProject(projName);
			
			if (msg!=null) return;
			
			//set project tree
			contTree.addProject(projName);
			createProjectGui(projName);
		});
		workSpaceTabPane.getSelectionModel().selectedItemProperty().addListener((ov, oldTab, newTab) -> {
			//******main code for changing project********
			if (newTab==null) {
				setProjectNull();
			}
			else {
				mainClass.projectManager.setActiveProject(newTab.getText());
				
				
				workTabContent.updateWorkScene();
				
				comboProject.getSelectionModel().select(newTab.getText());
				//update calculation list
				comboCalculation.getItems().clear();
				//current calculation exists, so at least one calculation exists
				if (mainClass.projectManager.existCurrentCalc()) {
					ArrayList<String> al = mainClass.projectManager.getCurrentCalcList();
					for (String ec : al) {
						comboCalculation.getItems().add(ec);//******later, organize/sort the items
					}
					openCalc(mainClass.projectManager.getCurrentCalcName());
				}
				else {
					//******not the most efficient way, may run twice
					radioGeometry.setSelected(true);
					toggleGeometry();
				}
			}
	    });
		comboProject.getSelectionModel().selectedItemProperty().addListener((ov, oldVal, newVal) -> {
			if (newVal!=null) {
				//-------------********not the most efficient way*******---------------
				//will bounce between comboProject and workSpaceTabPane
				//no need to put the code executed when changing project again here!
				workSpaceTabPane.getSelectionModel().select(projectTabDict.get(newVal));
//				mainClass.projectManager.setActiveProject(newVal);
				openCalc(mainClass.projectManager.getCurrentCalcName());//openCalc is null tolerant
				
			}
	    });
		comboCalculation.getSelectionModel().selectedItemProperty().addListener((ov, oldVal, newVal) -> {
			if (newVal!=null && !newVal.isEmpty()) {
				mainClass.projectManager.setActiveCalculation(newVal);
				//-------------********not the most efficient way*******---------------
				openCalc(mainClass.projectManager.getCurrentCalcName());//openCalc is null tolerant
			}
	    });
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
		showInputButton.setOnAction((event) -> {
			ArrayList<ContainerInputString> cis = mainClass.projectManager.genInputFromAgent();
			
			if(!mainClass.isTestMode()) {
				if (cis!=null && cis.size()>0) {
					for(int i=0;i<cis.size();i++) {
						ShowAlert.showAlert(AlertType.INFORMATION, "Input", cis.size()+
								" steps in total. Show now the input for the "+Integer.toString(i)+"th step:\n"+cis.get(i).toString());
					}
				}
				else {
					ShowAlert.showAlert(AlertType.INFORMATION, "Input", "Cannot generate input file. Empty input file.");
				}
			}
		});
		
		//new thread listening to job status
		thread1 = new Thread() {
	        public void run() {
        		try {
		            while (!interrupted()) {        
	                    //sleep
	                    Thread.sleep(500);
		                
		                // update currentJobLabel on FX thread
		                Platform.runLater(new Runnable() {
		
		                    public void run() {
		                    	String st = mainClass.jobManager.getCurrentJobName();
		                    	if(st==null) {currentJobLabel.setText("Idle...");}
		                    	else {currentJobLabel.setText("Running: "+st);}
		                    }
		                });
		            }
        		} catch (InterruptedException ex) {
                    //ex.printStackTrace();
                }
	        }
        };
        thread1.start();
        
		stopCurrentJob.setOnAction((event) -> {
			mainClass.jobManager.stopCurrent();
		});
		stopAllJobs.setOnAction((event) -> {
			mainClass.jobManager.stopAll();
		});
		runJob.setOnAction((event) -> {
//			mainClass.jobManager.addNode(new JobNode(null,"notepad.exe"));
//			mainClass.jobManager.addNode(new JobNode("C:\\Program Files\\PuTTY\\","putty.exe"));
//			mainClass.jobManager.addNode(new JobNode(null,"notepad.exe"));
			//save project first
			File wsDir = mainClass.projectManager.getWorkSpaceDir();
			if(wsDir==null || !wsDir.canWrite()) {
				ShowAlert.showAlert(AlertType.INFORMATION, "Error", "Cannot find the workspace directory when trying to run job.");
		    	return;
	    	}
			//only save current calc, do not show successfully save window
			mainClass.projectManager.saveActiveProjectInMultipleFiles(wsDir,true,false);
			//get calculation directory
			File fl = mainClass.projectManager.getCalculationDir();
			if(fl==null || !fl.canWrite() || !fl.canRead()) {
				ShowAlert.showAlert(AlertType.INFORMATION, "Error", "Cannot find the calculation directory when trying to run job.");
		    	return;
			}

			//generate input file
			ArrayList<ContainerInputString> cis = mainClass.projectManager.genInputFromAgent();
			if(cis==null || cis.isEmpty()) {
				ShowAlert.showAlert(AlertType.INFORMATION, "Error", "No input file generated. Should not be like this! Abort...");
		    	return;
			}

			for(int j = 0 ; j < cis.size() ; j++) {
				if(cis.get(j)==null || (cis.get(j).log!=null && !cis.get(j).log.isEmpty()) || cis.get(j).input==null) {
					String stt = "Warning! Input file not complete for "+j+"th step. Please fix the following errors:\n";
			    	stt+=(cis.get(j).input==null? "Null input string.\n":"");
					ShowAlert.showAlert(AlertType.INFORMATION, "Warning", cis.get(j)==null ? stt:(stt + cis.get(j).log));
			    	return;
				}
				if(cis.get(j).stepName==null) {
					ShowAlert.showAlert(AlertType.INFORMATION, "Warning", "Warning! EnumStep not set for "+j+"th step. Please check the code.");
			    	return;
				}
				File calcFile = new File(fl,cis.get(j).stepName.toString()+".in");
				try {
		            Files.write(calcFile.toPath(), cis.get(j).input.getBytes());
		        } catch (IOException e) {
		        	ShowAlert.showAlert(AlertType.INFORMATION, "Error", "Warning! Cannot write input file for "+j+"th step. Abort.");
			    	return;
		        }
			}
			//check QE path
			if(mainClass.projectManager.qePath==null || mainClass.projectManager.qePath.isEmpty()) {
				ShowAlert.showAlert(AlertType.INFORMATION, "Error", 
						"Cannot execute job because cannot qePath is null/empty. Please define the qePath in the Settings menu!");
				return;
			}
			
			final String postFixCommand;
			if(new File(mainClass.projectManager.qePath+File.separator+"pw.exe").canExecute()) {
				postFixCommand = ".exe";
			}else if(new File(mainClass.projectManager.qePath+File.separator+"pw.x").canExecute()) {
				postFixCommand = ".x";
			}
			else {
				ShowAlert.showAlert(AlertType.INFORMATION, "Error", 
						"Cannot execute job because cannot find pw.x/pw.exe in the qePath. Please verify the qePath in the Settings menu!");
				postFixCommand=null;
				return;
			}
			
			//start running the jobs
			for(int j = 0 ; j < cis.size() ; j++) {
				if(cis.get(j).commandName==null || cis.get(j).commandName.isEmpty()) {
					ShowAlert.showAlert(AlertType.INFORMATION, "Error", 
							"No command name specified for the "+Integer.toString(j)+"th step. Skip this step...");
					continue;
				}
				mainClass.jobManager.addNode(new JobNode(fl.getPath(),
						mainClass.projectManager.qePath+File.separator+cis.get(j).commandName+postFixCommand,cis.get(j).stepName.toString()));
			}
			
			//just for test use
//	    	mainClass.jobManager.addNode(new JobNode(null,"notepad.exe"));
			
		});

		saveProjectButton.setOnAction((event) -> {
			mainClass.projectManager.saveActiveProjectInMultipleFiles();
		});
		menuSaveProjectAs.setOnAction((event) -> {
			
			DirectoryChooser dirChooser = new DirectoryChooser ();
			dirChooser.setTitle("Choose an alternative workspace folder to save the project");
			
			//go to current directory
			String currentPath = Paths.get(".").toAbsolutePath().normalize().toString();
			File tmpFile = new File(currentPath);
			if(tmpFile.canRead()) {
				dirChooser.setInitialDirectory(tmpFile);
			}
			
			File selectedDir = dirChooser.showDialog((Stage)rootPane.getScene().getWindow());
			
			if(selectedDir!=null && selectedDir.canWrite()) {
				mainClass.projectManager.saveActiveProjectInMultipleFiles(selectedDir);
			}
		});
		menuLoadProject.setOnAction((event) -> {
//			File wsDir = getWorkSpaceDir();
//			if(wsDir==null || !wsDir.canWrite()) {return;}
//			
//			FileChooser fileChooser = new FileChooser();
//			fileChooser.setInitialDirectory(wsDir);
//			fileChooser.getExtensionFilters().addAll(new FileChooser.ExtensionFilter("project files", "*.proj"));
//			
//			File selectedFile = fileChooser.showOpenDialog((Stage)rootPane.getScene().getWindow());
//			
//			loadProject(selectedFile);
			
		});
		menuAbout.setOnAction((event) -> {
			Alert alert1 = new Alert(AlertType.INFORMATION);
	    	alert1.setTitle("License");
	    	alert1.setHeaderText("About");
	    	alert1.setContentText("Copyright (c) 2020 Haonan Huang.\r\n" + 
	    			"\r\n" + 
	    			"QuantumVITAS (Quantum Visualization Interactive Toolkit for Ab-initio Simulations) is free software; you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or any later version.\r\n" + 
	    			"\r\n" + 
	    			"QuantumVITAS is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.\r\n" + 
	    			"\r\n" + 
	    			"You should have received a copy of the GNU General Public License along with QuantumVITAS. If not, see https://www.gnu.org/licenses/gpl-3.0.txt.");
	    	alert1.showAndWait();
		});
		
		Scene sceneSettings = new Scene(borderSettings);
        Stage stageSettings = new Stage();
        stageSettings.setTitle("Settings");
        stageSettings.initModality(Modality.APPLICATION_MODAL);
        stageSettings.initStyle(StageStyle.DECORATED);
        stageSettings.setScene(sceneSettings);
        
		settingsMenuItem.setOnAction((event) -> {
	        stageSettings.showAndWait();
		});
		
		buttonOpenWorkSpace.setOnAction((event) -> {
			File selectedDir=null;	
			if(mainClass.isTestMode()) {
				//for testFX tests
				//go to current directory
				String currentPath = Paths.get(".").toAbsolutePath().normalize().toString();
				File tmpFile = new File(currentPath,"testfx");
				//delete test workspace folder
				if(tmpFile.exists()) {deleteDir(tmpFile);}
				//make new folder
				if(!tmpFile.exists() && !tmpFile.mkdirs()) {return;}
				selectedDir = tmpFile;
				
			}
			else {
				//only execute when there is not test
				String wsp1 = mainClass.projectManager.readGlobalSettings(SettingKeys.workspace.toString());
				if(wsp1!=null) {
					File wsDir = new File(wsp1);
					if(mainClass.projectManager.existCurrentProject() && wsDir.canRead()) {
						ShowAlert.showAlert(AlertType.INFORMATION, "Warning", "Please close ALL projects before changing the workspace directory.");
				    	return;
					}
				}
				
				DirectoryChooser dirChooser = new DirectoryChooser ();
				
				//go to current directory
				String currentPath = Paths.get(".").toAbsolutePath().normalize().toString();
				File tmpFile = new File(currentPath);
				if(tmpFile.canRead()) {
					dirChooser.setInitialDirectory(tmpFile);
				}
				
				selectedDir = dirChooser.showDialog((Stage)rootPane.getScene().getWindow());
			}
			if(selectedDir!=null && selectedDir.canRead()) {
				mainClass.projectManager.workSpacePath = selectedDir.getPath();
				textWorkSpace.setText(mainClass.projectManager.workSpacePath);
				mainClass.projectManager.writeGlobalSettings(SettingKeys.workspace.toString(),selectedDir.getPath());
				setWorkSpace(true);
				contTree.updateProjects(true);
				textWorkSpace.setBackground(new Background(new BackgroundFill(Coloring.validFile, 
						CornerRadii.EMPTY, Insets.EMPTY)));
			}
			
		});
		
	}
	
	public void killAllThreads() {
		thread1.interrupt();
	}
	private void loadEnvironmentPaths() {
		//surpress all Alerts for tests
		//load environment variable
		String wsp = mainClass.projectManager.readGlobalSettings(SettingKeys.workspace.toString());
		mainClass.projectManager.workSpacePath = wsp;
		if (wsp!=null) {
			File wsDir = new File(wsp);
			if(wsDir.canRead()) {
				textWorkSpace.setText(wsp);
				textWorkSpace.setBackground(new Background(new BackgroundFill(Coloring.validFile, 
						CornerRadii.EMPTY, Insets.EMPTY)));
				setWorkSpace(true);
			}
			else {
				setWorkSpace(false);
				textWorkSpace.setBackground(new Background(new BackgroundFill(Coloring.invalidFile, 
						CornerRadii.EMPTY, Insets.EMPTY)));
//				Alert alert1 = new Alert(AlertType.INFORMATION);
//		    	alert1.setTitle("Warning");
//		    	alert1.setContentText("Cannot load the previous workspace directory. Please specify a new one.");
//		    	alert1.showAndWait();
			}
		}
		else {
			setWorkSpace(false);
			textWorkSpace.setBackground(new Background(new BackgroundFill(Coloring.invalidFile, 
					CornerRadii.EMPTY, Insets.EMPTY)));
//			Alert alert1 = new Alert(AlertType.INFORMATION);
//	    	alert1.setTitle("Message");
//	    	alert1.setContentText("Please specify a workspace directory to start with.");
//	    	alert1.showAndWait();
		}
		
		String qePath = mainClass.projectManager.readGlobalSettings(SettingKeys.qePath.toString());
		mainClass.projectManager.qePath = qePath;
		
		
		contTree.updateProjects(false);
		
		String wsp2 = mainClass.projectManager.readGlobalSettings(SettingKeys.pseudolibroot.toString());
		mainClass.projectManager.pseudoLibPath = wsp2;
	}

	private void closeProject(String pj) {
		String tmp = mainClass.projectManager.removeProject(pj);
		if(tmp!=null) return;//cannot remove project: pj==null || pj is empty or pj not in the list
		Tab tab = projectTabDict.get(pj);
		if(tab!=null) {workSpaceTabPane.getTabs().remove(tab);}
		contTree.closeProject(pj);
		projectTabDict.remove(pj);
		comboProject.getItems().remove(pj);
		//openCalc(null);//not necessary. Covered by the change tab listener
		contTree.setOpenCloseButtons(true);
	}
	
	
	private void setWorkSpace(boolean bl) {
		if (bl) {
			for (Node node : rootPane.getChildrenUnmodifiable()) {
				node.setDisable(false);
		    }
			for (Node node : buttonOpenWorkSpace.getParent().getParent().getChildrenUnmodifiable()) {
				node.setDisable(false);
		    }
			for (Node node : buttonOpenWorkSpace.getParent().getChildrenUnmodifiable()) {
				node.setDisable(false);
		    }
		}
		else{
			for (Node node : rootPane.getChildrenUnmodifiable()) {
				node.setDisable(true);
		    }
			buttonOpenWorkSpace.getParent().getParent().setDisable(false);
			for (Node node : buttonOpenWorkSpace.getParent().getParent().getChildrenUnmodifiable()) {
				node.setDisable(true);
		    }
			buttonOpenWorkSpace.getParent().setDisable(false);
			for (Node node : buttonOpenWorkSpace.getParent().getChildrenUnmodifiable()) {
				node.setDisable(true);
		    }
			buttonOpenWorkSpace.setDisable(false);
			textWorkSpace.setDisable(false);
		}
	}
	private void toggleGeometry() {
		if (tabPaneRight==null) return;
		if (radioGeometry.isSelected()) 
		{
			if (!mainClass.projectManager.existCurrentProject()) return;//abnormal!
			//radioGeometry.setSelected(true);
			mainClass.projectManager.setGeoActive(true);
			
			Tab tab = new Tab();
			tab.setText(EnumStep.GEO.getName());
			tab.setContent(scrollGeo);
			tabPaneRight.getTabs().clear();
			tabPaneRight.getTabs().add(tab);
			contGeo.loadProjectParameters();
			contGeo.setEnabled();
			calcLabel.setText("Geometry");
			comboCalculation.setValue("");
			if (!tabPaneStatusRight) {
				hboxRight.getChildren().add(0,tabPaneRight);
				tabPaneStatusRight = true;
			}
		}
		else {
			openCalc(mainClass.projectManager.getCurrentCalcName());
		}
		
	}
	public void addRightPane(ScrollPane scroll,EnumStep es) {
		if (tabPaneRight==null) return;
		
		Tab tab = new Tab();
		tab.setText(es.getName());
		tab.setContent(scroll);
		tabPaneRight.getTabs().add(tab);
		
		if (!tabPaneStatusRight) {
			hboxRight.getChildren().add(0,tabPaneRight);
			tabPaneStatusRight = true;
		}
	}
	public void clearRightPane() {
		if (tabPaneRight!=null) {
			tabPaneRight.getTabs().clear();
		}
		if (tabPaneStatusRight) {
			hboxRight.getChildren().remove(tabPaneRight);
		}
		tabPaneStatusRight = false;
	}
	private void setProjectNull() {
		mainClass.projectManager.setActiveProject(null);
		calcMain.setDisable(true);
		runJob.setDisable(true);
		clearRightPane();
		comboCalculation.getItems().clear();
		radioGeometry.setSelected(true);
		calcLabel.setText("");
	}
	
	private void initializeLeftRightPane() {
		
		// right part, default off
		tabPaneStatusRight = false;
		VBox vboxRight = new VBox();
		
		//set label of the right button
		Button btnRight = new Button();
		Label labelRight  = new Label("Input Settings");
		labelRight.setRotate(-90);
		btnRight.setGraphic(new Group(labelRight));
		
		vboxRight.getChildren().add(btnRight);
		hboxRight.getChildren().add(vboxRight);
		//right part, tab pane
		tabPaneRight = new TabPane();tabPaneRight.setId("idtabPaneRight");
		//Tab tab = new Tab("3e");
		//tabPaneRight.getTabs().add(tab);
		tabPaneRight.setPrefSize(375, 300);
		tabPaneRight.setMinSize(150, 150);
		tabPaneRight.setTabClosingPolicy(TabClosingPolicy.UNAVAILABLE);
		//hboxRight.getChildren().add(0,tabPaneRight);
		
		//left part, default on
		scrollStatusLeft = true;
//		scrollLeft = new ScrollPane();
//		scrollLeft.setContent(projectTree);
		
		scrollLeft.setFitToHeight(true);
		VBox vboxLeft = new VBox();
		
		//set label of the left button
		Button btnLeft = new Button();
		Label labelLeft  = new Label("Project Treeview");
		labelLeft.setRotate(-90);
		btnLeft.setGraphic(new Group(labelLeft));
		
		vboxLeft.getChildren().add(btnLeft);
		hboxLeft.getChildren().addAll(vboxLeft,scrollLeft);
		
		//set button action
		btnRight.setOnAction((event) -> {
			if (tabPaneStatusRight) {
				hboxRight.getChildren().remove(tabPaneRight);
			}
			else {
				hboxRight.getChildren().add(0,tabPaneRight);
			}
			tabPaneStatusRight=!tabPaneStatusRight;
		});
		btnLeft.setOnAction((event) -> {
			if (scrollStatusLeft) hboxLeft.getChildren().remove(scrollLeft);
			else hboxLeft.getChildren().add(scrollLeft);
			scrollStatusLeft=!scrollStatusLeft;
		});
	}
	private void createProjectGui(String projName) {

		//add to ComboBox
		comboProject.getItems().add(projName);
		comboProject.setValue(projName);
		//add tab
		Tab tab = workTabContent.setUpTabContent();
		
		final String pj = projName;
		tab.setText(pj);
		tab.setClosable(true);
		tab.setOnClosed((e) -> {
			closeProject(pj);
		});
				
		//add tab
		projectTabDict.put(pj,tab);
		workSpaceTabPane.getTabs().add(tab);
		workSpaceTabPane.getSelectionModel().select(tab);//must happen AFTER projectTabDict.put(pj,tab), because updateWorkScene() uses this

		contTree.updateFullCalcTree();
		//allow more interactions
		calcMain.setDisable(false);
		runJob.setDisable(false);
		toggleGeometry();
	}
	private void openCalc(String ecStr) {
		
		//load an existing calculation having name String ecStr
		if (ecStr==null || ecStr.isEmpty()) {
			clearRightPane();
			comboCalculation.getItems().clear();
			calcLabel.setText("");
			return;
		}

		mainClass.projectManager.setActiveCalculation(ecStr);
		 
		//check again whether successfully set the active calculation
		if(!ecStr.equals(mainClass.projectManager.getCurrentCalcName())) {
			Alert alert = new Alert(AlertType.INFORMATION);
	    	alert.setTitle("Error");
	    	alert.setContentText("Cannot set active calculation string ecStr.");
	    	alert.showAndWait();
	    	return;
		}
		EnumCalc ec = mainClass.projectManager.getCurrentCalcType();//null safe
		openCalc(ec, false);
		
	}
	private void openCalc(EnumCalc ec, boolean boolCreate) {
		//if(boolCreate), open a new calculation of type EnumCalc ec
		//if(!boolCreate), just load one existing calculation. MUST be entered through openCalc(String ecStr) in this case!
		if (ec==null) {return;}
		
		if (!mainClass.projectManager.existCurrentProject()) return;//abnormal!
		radioCalculation.setSelected(true);
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
			enumStepArray = new EnumStep[] {EnumStep.SCF,EnumStep.NSCF,EnumStep.DOS};
			addCalc(boolCreate, ec, enumStepArray);
			break;
		case BANDS:
			enumStepArray = new EnumStep[] {EnumStep.SCF,EnumStep.BANDS};
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
		default:
			ShowAlert.showAlert(AlertType.INFORMATION, "Error", "Wrong calculation type!");
		}
	}
	private void addCalc(boolean boolCreate, EnumCalc enumCalcThis, EnumStep[] enumStepArray) {
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
			//add comboBox item
			comboCalculation.getItems().add(calcName);
			//update current status to trees
			contTree.updateCalcTree(calcName);
			
		}
		
		//prepare to load GUI
		clearRightPane();
		addRightPane(scrollGeo,EnumStep.GEO);
		
		//load parameters for current project and calculation as well as update GUI
		contGeo.loadProjectParameters();
		contGeo.setDisabled();
		for (int i=0;i<lengthArray;i++) {
			switch(enumStepArray[i]) {
				case SCF:contScf.loadProjectParameters();addRightPane(scrollScf,enumStepArray[i]);break;
				case OPT:contOpt.loadProjectParameters();addRightPane(scrollOpt,enumStepArray[i]);break;
				case BOMD:contMd.loadProjectParameters();addRightPane(scrollMd,enumStepArray[i]);break;
				case NSCF:contNscf.loadProjectParameters();addRightPane(scrollNscf,enumStepArray[i]);break;
				case DOS:contDos.loadProjectParameters();addRightPane(scrollDos,enumStepArray[i]);break;
				case TDDFT:
					contTddft.loadProjectParameters();addRightPane(scrollTddft,enumStepArray[i]);
					break;
				case BANDS:
					contBands.loadProjectParameters();addRightPane(scrollBands,enumStepArray[i]);
					break;
				default:ShowAlert.showAlert(AlertType.INFORMATION, "Error", 
						"Nonimplemented controller: "+(enumStepArray[i]==null?"null":enumStepArray[i].toString()));break;
			}
		}

		try {tabPaneRight.getSelectionModel().select(1);}catch (Exception e) {}//load second tab(not geo)
		
		calcLabel.setText(enumCalcThis.getLong());
		calcName = mainClass.projectManager.getCurrentCalcName();
		if(calcName!=null) comboCalculation.getSelectionModel().select(calcName);
	}
	private boolean deleteDir(File directoryToBeDeleted) {
	    File[] allContents = directoryToBeDeleted.listFiles();
	    if (allContents != null) {
	        for (File file : allContents) {
	        	deleteDir(file);
	        }
	    }
	    return directoryToBeDeleted.delete();
	}
}
