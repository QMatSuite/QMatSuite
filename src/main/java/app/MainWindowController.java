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


import java.awt.Desktop;
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
import javafx.scene.control.ButtonType;
import javafx.scene.control.ContextMenu;
import javafx.scene.control.Label;
import javafx.scene.control.Menu;
import javafx.scene.control.MenuItem;
import javafx.scene.control.ScrollPane;
import javafx.scene.control.SplitPane;
import javafx.scene.control.Tab;
import javafx.scene.control.TabPane;
import javafx.scene.control.TabPane.TabClosingPolicy;
import javafx.scene.control.TextArea;
import javafx.scene.control.TextField;
import javafx.scene.control.TextInputDialog;
import javafx.scene.control.TreeItem;
import javafx.scene.layout.AnchorPane;
import javafx.scene.layout.Background;
import javafx.scene.layout.BackgroundFill;
import javafx.scene.layout.BorderPane;
import javafx.scene.layout.CornerRadii;
import javafx.scene.layout.HBox;
import javafx.scene.layout.VBox;
import javafx.stage.DirectoryChooser;
import javafx.stage.Modality;
import javafx.stage.Stage;
import javafx.stage.StageStyle;
import main.MainClass;
import project.ProjectCalcLog;
import project.ProjectManager;
import app.centerwindow.OutputViewerController;
import app.centerwindow.WorkScene3D;
import app.input.InputBandsController;
import app.input.InputDosController;
import app.input.InputGeoController;
import app.input.InputMdController;
import app.input.InputNebController;
import app.input.InputNscfController;
import app.input.InputOptController;
import app.input.InputPhononController;
import app.input.InputScfController;
import app.input.InputTddftController;
import app.menus.SettingsWindowController;
import com.consts.Constants.EnumCalc;
import com.consts.Constants.EnumOccupations;
import com.consts.Constants.EnumStep;
import com.env.SystemInfo;
import com.error.ErrorMsg;
import com.error.ShowAlert;
import com.programconst.Coloring;
import com.programconst.DefaultFileNames;
import com.programconst.ProgrammingConsts;
import com.programconst.DefaultFileNames.SettingKeys;
import com.programconst.ProgrammingConsts.PathSettings;
import agent.InputAgentScf;
import input.ContainerInputString;
import job.JobManager;
import job.JobNode;

public class MainWindowController implements Initializable{
	
	@FXML private BorderPane basePane;
	
    @FXML private Menu menuFile;

    @FXML private MenuItem menuAbout,
    menuSaveProjectAs;
    
    @FXML private MenuItem stopCurrentJob,
    stopAllJobs,
    settingsMenuItem;
    
    @FXML private Button showInputButton,
    runJob,
    buttonOpenWorkSpace,
    saveProjectButton,
    openQEPathButton,
    buttonOpenLib;//buttonOpenInWindows
    
    @FXML private TextField textWorkSpace,
    textQEPath,
    labelPathPseudoLib;
    
	@FXML private ScrollPane inputField;
	
	@FXML private HBox hboxRight,
	hboxLeft;
	
	@FXML private Label calcLabel,
	currentJobLabel;
	
	@FXML private TabPane workSpaceTabPane;
	
	
	@FXML private BorderPane rootPane;
	
	
	private ScrollPane scrollGeo,
	scrollOpt,
	scrollScf,
	scrollDos,
	scrollNscf,
	scrollBands,
	scrollMd,
	scrollTddft,
	scrollBandsPP,
	scrollPhonon,
	scrollNeb;
	
	private ScrollPane scrollLeft;
	
	private BorderPane borderSettings,
	borderRun;
	
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
	
	private InputPhononController contPhonon;
	
	private InputNebController contNeb;
			
	private MainLeftPaneController contTree;
	
	private InputBandsController contBands;
	
	private SettingsWindowController contSettings;
	
	private OutputViewerController contOutput;
	
	private JobDialogController contRun;
	
	private SplitPane splitOutput;
	
	private HashMap<String, Tab> projectTabDict;
	
	private Thread thread1;
			
	public MainWindowController(MainClass mc) {
		mainClass = mc;
	}
	private void selectGeoCalc(TreeItem<ProjectCalcLog> newValue, String pj) {
		if(pj.equals(newValue.getValue().getProject())) {
			//root project treeitem. Go to geometry
			toggleGeometry();
		}
		else {
			String calcNameTmp = newValue.getValue().getCalculation();
			openCalc(calcNameTmp);
			contOutput.calculationFolderChange(calcNameTmp);
		}
	}
	@Override
	public void initialize(URL arg0, ResourceBundle arg1){
		workSpaceTabPane.setTabClosingPolicy(TabClosingPolicy.SELECTED_TAB);
		
		projectTabDict = new HashMap<String, Tab>();
		
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
			
			scrollBandsPP = new ScrollPane(new Label("Nothing to control in this step."));

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
			
			contOutput = new OutputViewerController(mainClass,contGeo);
			fxmlLoader = new FXMLLoader(getClass().getClassLoader().getResource("app/centerwindow/outputViewer.fxml"));
			fxmlLoader.setController(contOutput);
			splitOutput = fxmlLoader.load();
			
			
		} catch (IOException e) {
			// TODO Auto-generated catch block
			e.printStackTrace();
		}
		
		splitOutput.prefWidthProperty().bind(workSpaceTabPane.widthProperty());
		splitOutput.prefHeightProperty().bind(workSpaceTabPane.heightProperty());
		
		//workTabContent =  new WorkTabContent(mainClass,workSpaceTabPane,projectTabDict,contGeo);
		
		//textWorkSpace.setDisable(true);
		textWorkSpace.setEditable(false);
		//set the style of workspace and QEEngine fields
		textWorkSpace.setBackground(new Background(new BackgroundFill(Coloring.defaultFile, 
				CornerRadii.EMPTY, Insets.EMPTY)));
		//set contextmenu
		ContextMenu contextWsp = new ContextMenu();
        MenuItem contextMenuWsp = new MenuItem("Open with external");
        contextWsp.getItems().add(contextMenuWsp);
        textWorkSpace.setContextMenu(contextWsp);
        contextMenuWsp.setOnAction((event) -> {
			File wsDir = mainClass.projectManager.getWorkSpaceDir();
			
			if(wsDir==null || !wsDir.canRead()) {return;}
			if( Desktop.isDesktopSupported() )
			{
				new Thread(() -> {
				   try {
				       Desktop.getDesktop().open(wsDir);
				   } catch (IOException e1) {
				       e1.printStackTrace();
				   }
			       }).start();
			}
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
				String wsp1 = ProjectManager.readGlobalSettings(SettingKeys.workspace.toString());
				if(wsp1!=null) {
					File wsDir = new File(wsp1);
					if(mainClass.projectManager.existCurrentProject() && wsDir.canRead()) {
						ShowAlert.showAlert(AlertType.INFORMATION, "Warning", "Please close ALL projects before changing the workspace directory.");
				    	return;
					}
				}
				
				DirectoryChooser dirChooser = new DirectoryChooser ();
				
				//go to current directory
				chooseInitialDir(dirChooser, this.textWorkSpace.getText());
				
				selectedDir = dirChooser.showDialog((Stage)rootPane.getScene().getWindow());
			}
			if(selectedDir!=null && selectedDir.canRead()) {
				//mainClass.projectManager.workSpacePath = selectedDir.getPath();
				//textWorkSpace.setText(mainClass.projectManager.workSpacePath);
				String pathWritten = ProjectManager.writePathSettings(SettingKeys.workspace.toString(),selectedDir.getPath());
				setTexFieldPath(textWorkSpace, pathWritten,PathSettings.workspace);
				mainClass.projectManager.workSpacePath = pathWritten;
				
				setWorkSpace(true);
				contTree.updateProjects(true);
				//textWorkSpace.setBackground(new Background(new BackgroundFill(Coloring.validFile, 
				//		CornerRadii.EMPTY, Insets.EMPTY)));
			}
			
		});
        
        textQEPath.setEditable(false);
        textQEPath.setBackground(new Background(new BackgroundFill(Coloring.defaultFile, 
				CornerRadii.EMPTY, Insets.EMPTY)));
        //set contextmenu
  		ContextMenu contextQe = new ContextMenu();
        MenuItem contextMenuQe = new MenuItem("Open with external");
        contextQe.getItems().add(contextMenuQe);
        textQEPath.setContextMenu(contextQe);
        contextMenuQe.setOnAction((event) -> {
        	File qeDir = new File(mainClass.projectManager.qePath);
  			
        	if(qeDir==null || !qeDir.canRead()) {
        		
        		return;}
        	if( Desktop.isDesktopSupported() )
			{
			    new Thread(() -> {
				   try {
				       Desktop.getDesktop().open(qeDir);
				   } catch (IOException e1) {
				       e1.printStackTrace();
				   }
			       }).start();
			}
  		});
		openQEPathButton.setOnAction((event) -> {

			DirectoryChooser dirChooser = new DirectoryChooser ();
			
			//go to current directory

			chooseInitialDir(dirChooser, textQEPath.getText());
			
			File selectedDir = dirChooser.showDialog((Stage)rootPane.getScene().getWindow());
			
			if(selectedDir!=null && selectedDir.canRead()) {
				String selectedPathStr = selectedDir.getPath();
				if(!isQePathValid(selectedDir)) {
					if(isQePathValid(new File(selectedDir,"qe"))) {
						selectedPathStr = new File(selectedDir,"qe").getPath();
					}
					else if(isQePathValid(new File(selectedDir,"bin"))) {
						selectedPathStr = new File(selectedDir,"bin").getPath();
					}
				}
				
				String pathWritten = ProjectManager.writePathSettings(SettingKeys.qePath.toString(),selectedPathStr);
				mainClass.projectManager.qePath = pathWritten;
				setTexFieldPath(textQEPath, pathWritten,PathSettings.qe);
			}
			
		});
		
		
		labelPathPseudoLib.setEditable(false);
		labelPathPseudoLib.setBackground(new Background(new BackgroundFill(Coloring.defaultFile, 
				CornerRadii.EMPTY, Insets.EMPTY)));
        //set contextmenu
  		ContextMenu contextPp = new ContextMenu();
        MenuItem contextMenuPp = new MenuItem("Open with external");
        contextPp.getItems().add(contextMenuPp);
        labelPathPseudoLib.setContextMenu(contextPp);
        contextMenuPp.setOnAction((event) -> {
        	File ppDir = new File(mainClass.projectManager.getPseudoLibPath());
  			
        	if(ppDir==null || !ppDir.canRead()) {
        		
        		return;}
        	if( Desktop.isDesktopSupported() )
			{
			    new Thread(() -> {
				   try {
				       Desktop.getDesktop().open(ppDir);
				   } catch (IOException e1) {
				       e1.printStackTrace();
				   }
			       }).start();
			}
  		});
        //open folder chooser for pseudoLib
    	buttonOpenLib.setOnAction((event) -> {	
			
			DirectoryChooser dirChooser = new DirectoryChooser ();
			
			//go to current directory
			chooseInitialDir(dirChooser, this.labelPathPseudoLib.getText());
			
			File selectedDir = dirChooser.showDialog((Stage)rootPane.getScene().getWindow());
			
			if(selectedDir!=null && selectedDir.canRead()) {
				
				String fieldName = ProjectManager.writePathSettings(SettingKeys.pseudolibroot.toString(),selectedDir.getPath());
				setTexFieldPath(labelPathPseudoLib, fieldName,PathSettings.pplib);
				mainClass.projectManager.setPseudoLibPath(fieldName);
				
//				InputAgentGeo iGeo = (InputAgentGeo) mainClass.projectManager.getCurrentGeoAgent();
//				if (iGeo!=null) {iGeo.pseudodir = selectedDir.getPath();}
				
				//update the path
				contGeo.updatePseudoElementList();
			}
		});
        
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
		contTree.projectTree.getSelectionModel().selectedItemProperty().addListener((v, oldValue, newValue) -> { 
			contTree.setOpenCloseButtons(false);
			if (newValue!=null) {
				//no project selected
				String pj = contTree.getSelectedProject();
				if(pj==null || pj.isEmpty()) {return;}
				
				if(pj.equals(mainClass.projectManager.getActiveProjectName())) {
					//project already loaded and active. Check whether is root project treeitem or calculations
					//ShowAlert.showAlert(AlertType.INFORMATION, "Debug", newValue.getValue().getProject()+","+newValue.getValue().getCalculation()+","+pj);
					selectGeoCalc(newValue, pj);
				}
				else {
					//project not the current one
					if(mainClass.projectManager.containsProject(pj)) {
						//project already opened, but not the current one. Change current project
						//ShowAlert.showAlert(AlertType.INFORMATION, "Debug", newValue.getValue().getProject()+","+newValue.getValue().getCalculation()+","+pj);
						workSpaceTabPane.getSelectionModel().select(projectTabDict.get(pj));
						//project now active. Check whether is root project treeitem or calculations
						selectGeoCalc(newValue, pj);
					}
					else {
						//project not opened. Allow open button to work
						Tab tabTmp = workSpaceTabPane.getSelectionModel().getSelectedItem();
						if(tabTmp!=null) {
							TextField tf = new TextField("Selected project not opened yet. Please use the 'open project' button on the left panel before continuing.");
							tabTmp.setContent(tf);
						}
						contTree.setOpenCloseButtons(true);
						return;
					}
					
				}
			}
		});
		
		
		setProjectNull();
		
		initializeLeftRightPane();//initialize tabPaneRight
		
		loadEnvironmentPaths();
		
		contTree.createProject.setOnAction((event) -> {
			
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
				//ShowAlert.showAlert(AlertType.INFORMATION, "Debug", newTab.getText()+","+contTree.getSelectedProject());
				mainClass.projectManager.setActiveProject(newTab.getText());
				
				//workTabContent.updateWorkScene();

				//only try to select the treeitem if the selection change of the workspacetabpane does not come from 
				//user selecting treeitem.
				if(!newTab.getText().equals(contTree.getSelectedProject())) {
					if (mainClass.projectManager.existCurrentCalc()) {
						contTree.selectCalc(newTab.getText(),mainClass.projectManager.getCurrentCalcName());
					}
					else {
						contTree.selectProj(newTab.getText());
					}
				}
			}
	    });
		contTree.calcScf.setOnAction((event) -> {
			openCalc(EnumCalc.SCF,true);
		});
		contTree.calcOpt.setOnAction((event) -> {
			openCalc(EnumCalc.OPT,true);
		});
		contTree.calcDos.setOnAction((event) -> {
			openCalc(EnumCalc.DOS,true);
		});
		contTree.calcBands.setOnAction((event) -> {
			openCalc(EnumCalc.BANDS,true);
		});
		contTree.calcMd.setOnAction((event) -> {
			openCalc(EnumCalc.BOMD,true);
		});
		contTree.calcTddft.setOnAction((event) -> {
			openCalc(EnumCalc.TDDFT,true);
		});
		contTree.calcPhonon.setOnAction((event) -> {
			openCalc(EnumCalc.PHONON,true);
		});
		contTree.calcNeb.setOnAction((event) -> {
			openCalc(EnumCalc.NEB,true);
		});
		contTree.calcCustom.setOnAction((event) -> {
			ShowAlert.showAlert(AlertType.INFORMATION, "Info", "Customized calculation not yet implemented.");
		});
		showInputButton.setOnAction((event) -> {
			ArrayList<ContainerInputString> cis = mainClass.projectManager.genInputFromAgent();
			
			if(!mainClass.isTestMode()) {
				if (cis!=null && cis.size()>0) {
					for(int i=0;i<cis.size();i++) {
						Alert alert = new Alert(AlertType.INFORMATION);
						alert.setHeaderText("Input");
						alert.setContentText(cis.size()+
								" steps in total. Show now the input for the "+Integer.toString(i+1)+"th step.");
						TextArea area = new TextArea(cis.get(i).toString());
						area.setWrapText(true);
						area.setEditable(false);

						alert.getDialogPane().setExpandableContent(area);
						alert.getDialogPane().setExpanded(true);
						alert.showAndWait();
						if(alert.getResult() == ButtonType.OK || alert.getResult() == ButtonType.YES) {
							continue;
						}
						else {
							break;
						}
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
		
		Scene sceneRun = new Scene(borderRun);
        Stage stageRun = new Stage();
        stageRun.setTitle("Job settings");
        stageRun.initModality(Modality.APPLICATION_MODAL);
        stageRun.initStyle(StageStyle.DECORATED);
        stageRun.setScene(sceneRun);
        stageRun.setResizable(false);
        
		runJob.setOnAction((event) -> {
//			mainClass.jobManager.addNode(new JobNode(null,"notepad.exe"));
//			mainClass.jobManager.addNode(new JobNode("C:\\Program Files\\PuTTY\\","putty.exe"));
//			mainClass.jobManager.addNode(new JobNode(null,"notepad.exe"));
			//check QE path
			if(mainClass.projectManager.qePath==null || mainClass.projectManager.qePath.isEmpty()) {
				ShowAlert.showAlert(AlertType.INFORMATION, "Error", 
						"Cannot execute job because cannot qePath is null/empty. Please define the qePath in the Settings menu!");
				return;
			}
			if(mainClass.projectManager.isGeoActive()) {
				ShowAlert.showAlert(AlertType.INFORMATION, "Error", "In the geometry page. Please go to one calculation "
						+ "page to start running the job.");
				return;
			}
			
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
				File calcFile = new File(fl,cis.get(j).stepName.toString()+ProgrammingConsts.stdinExtension);
				try {
		            Files.write(calcFile.toPath(), cis.get(j).input.getBytes());
		        } catch (IOException e) {
		        	ShowAlert.showAlert(AlertType.INFORMATION, "Error", "Warning! Cannot write input file for "+j+"th step. Abort.");
			    	return;
		        }
			}
			
			final String postFixCommand;
			
			if(SystemInfo.isWindows()) {
				if(!new File(mainClass.projectManager.qePath+File.separator+"pw.exe").canExecute()) {
					ShowAlert.showAlert(AlertType.INFORMATION, "Error", 
							"Windows detected. Cannot execute job because cannot find pw.exe in the qePath. Please verify the qePath!");
					return;
				}
				postFixCommand = ".exe";
			}else if(SystemInfo.isUnix()) {
				if(!new File(mainClass.projectManager.qePath+File.separator+"pw.x").canExecute()) {
					ShowAlert.showAlert(AlertType.INFORMATION, "Error", 
							"Linux/Unix detected. Cannot execute job because cannot find pw.x in the qePath. Please verify the qePath!");
					return;
				}
				postFixCommand = ".x";
			}
			else if(SystemInfo.isMac()){
				ShowAlert.showAlert(AlertType.INFORMATION, "Error", 
						"Mac detected. Currently not supported.");
				return;
			}
			else {	
				ShowAlert.showAlert(AlertType.INFORMATION, "Error", 
						"Unrecongized operating system: "+SystemInfo.getOSName()+". Cannot run job.");
				return;
			}
			
			//final settings
			contRun.initializeBoolRunStep(cis);
			stageRun.showAndWait();
			if(!contRun.isBoolRun()) {return;}
			ArrayList<Boolean> boolRunStep = contRun.getBoolRunStep();
			
			//read mpi settings
			String mpiCommand = "";
			if(SystemInfo.isWindows()) {
				if(JobManager.isBoolParallel()) {
					File qeRoot = new File(mainClass.projectManager.qePath).getParentFile();
					if(qeRoot!=null) {
						File mpiFile = new File(qeRoot+File.separator+"mpi"+File.separator+"mpiexec.exe");
						if(mpiFile.canExecute()) {
							mpiCommand = mpiFile.getAbsolutePath();
						}
					}
				}
			}else if(SystemInfo.isUnix()) {
				if(JobManager.isBoolParallel()) {
					mpiCommand = "mpirun";
				}
			}
			else if(SystemInfo.isMac()){
			}
			else {
			}
			
			//start running the jobs
			for(int j = 0 ; j < cis.size() ; j++) {
				if(j>=boolRunStep.size()) {ShowAlert.showAlert(AlertType.INFORMATION, "Error", "boolRunStep size too small.");break;}
				if(!boolRunStep.get(j)) {continue;}
				if(cis.get(j).commandName==null || cis.get(j).commandName.isEmpty()) {
					ShowAlert.showAlert(AlertType.INFORMATION, "Error", 
							"No command name specified for the "+Integer.toString(j)+"th step. Skip this step...");
					continue;
				}
				mainClass.jobManager.addNode(new JobNode(fl.getPath(),mpiCommand,
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
        stageSettings.setResizable(false);
        
		settingsMenuItem.setOnAction((event) -> {
	        stageSettings.showAndWait();
		});

		
	}
	
	public void killAllThreads() {
		thread1.interrupt();
	}
	private void loadEnvironmentPaths() {
		//***********not efficient. Read setting file three times!
		//surpress all Alerts for tests
		//load environment variable
		String wsp = ProjectManager.readGlobalSettings(SettingKeys.workspace.toString());
		mainClass.projectManager.workSpacePath = wsp;
		setTexFieldPath(textWorkSpace, wsp, PathSettings.workspace);
		setWorkSpace(wsp!=null && (new File(wsp)).canRead());
		
		String qePath = ProjectManager.readGlobalSettings(SettingKeys.qePath.toString());
		mainClass.projectManager.qePath = qePath;
		setTexFieldPath(textQEPath, qePath,PathSettings.qe);
		
		contTree.updateProjects(false);
		
		String wsp2 = ProjectManager.readGlobalSettings(SettingKeys.pseudolibroot.toString());
		mainClass.projectManager.setPseudoLibPath(wsp2);
		
		setTexFieldPath(labelPathPseudoLib, wsp2,PathSettings.pplib);

	}
	private boolean isQePathValid(File qeDir) {
		if(qeDir==null || !qeDir.canRead()) {return false;}
		return (SystemInfo.isUnix() && (new File(qeDir,"pw.x")).exists() )
				|| (SystemInfo.isWindows() &&(new File(qeDir,"pw.exe")).exists());
	}
	private void setTexFieldPath(TextField tf, String qePath, PathSettings ps) {
		if(qePath!=null) {
			tf.setText(qePath);
			File qeDir = new File(qePath);
			boolean isValid = qeDir.canRead();
			if(qeDir.canRead()) {
				switch(ps) {
					case qe:isValid = isQePathValid(qeDir);
							break;
					case pplib:isValid = ((new File(qeDir,DefaultFileNames.pseudoDojoDir)).exists() || 
							(new File(qeDir,DefaultFileNames.psLibraryDir)).exists() ||
							(new File(qeDir,DefaultFileNames.ssspDir)).exists());break;
					case workspace: isValid = true;break;
					default:ShowAlert.showAlert(AlertType.INFORMATION, "Error", "Unrecognized PathSettings!");return;
				}
			}
			if(isValid) {
				tf.setBackground(new Background(new BackgroundFill(Coloring.validFile, 
						CornerRadii.EMPTY, Insets.EMPTY)));
			}
			else {
				tf.setBackground(new Background(new BackgroundFill(Coloring.invalidFile, 
						CornerRadii.EMPTY, Insets.EMPTY)));
			}
		}
		else {
			tf.setText("null");
			tf.setBackground(new Background(new BackgroundFill(Coloring.invalidFile, 
					CornerRadii.EMPTY, Insets.EMPTY)));
		}
	}

	private void closeProject(String pj) {
		String tmp = mainClass.projectManager.removeProject(pj);
		if(tmp!=null) return;//cannot remove project: pj==null || pj is empty or pj not in the list
		Tab tab = projectTabDict.get(pj);
		if(tab!=null) {workSpaceTabPane.getTabs().remove(tab);}
		contTree.closeProject(pj);
		projectTabDict.remove(pj);
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
			//textWorkSpace.setDisable(false);
		}
	}
	private void toggleGeometry() {
		//now only toggle to geometry
		if (tabPaneRight==null) return;

		if (!mainClass.projectManager.existCurrentProject()) return;//abnormal!
		
		mainClass.projectManager.setGeoActive(true);
		
		//centerpane
		mainClass.projectManager.updateViewerPlot();//*******not always necessary?
		WorkScene3D workScene = mainClass.projectManager.getActiveProject().getViewer3D();
		workScene.centerSubScene(workSpaceTabPane);
		AnchorPane acp = workScene.getRootPane();
		Tab tabTmp = workSpaceTabPane.getSelectionModel().getSelectedItem();
		if(tabTmp!=null) {
			tabTmp.setContent(acp);
		}
		
		//right pane
		Tab tab = new Tab();
		tab.setText(EnumStep.GEO.getName());
		tab.setContent(scrollGeo);
		tabPaneRight.getTabs().clear();
		tabPaneRight.getTabs().add(tab);
		contGeo.loadProjectParameters();
		contGeo.setEnabled();
		calcLabel.setText("Geometry");
		if (!tabPaneStatusRight) {
			hboxRight.getChildren().add(0,tabPaneRight);
			tabPaneStatusRight = true;
		}
		
	}
	public void addRightPane(ScrollPane scroll,EnumStep es) {
		if (tabPaneRight==null) return;
		
		Tab tab = new Tab();
		//tab.setText(es.getName());
		tab.setText(es.toString());
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
		contTree.projectTree.getSelectionModel().clearSelection();
		contTree.calcMain.setDisable(true);
		showInputButton.setDisable(true);
		runJob.setDisable(true);
		clearRightPane();
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

		//add tab
		Tab tab = new Tab();
		
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

		contTree.updateFullCalcTree();//contains selecting calculations. MUST BE AFTER adding tabs
		
		//allow more interactions
		contTree.calcMain.setDisable(false);
		showInputButton.setDisable(false);
		runJob.setDisable(false);
		//this function was called twice:
		//1. contTree.buttonOpenSelected
		//2. createProject button
		//so anyhow it should toggle to the geometry
		//toggleGeometry(true);
	}
	private void openCalc(String ecStr) {
		
		//load an existing calculation having name String ecStr
		if (ecStr==null || ecStr.isEmpty()) {
			clearRightPane();
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
			contGeo.setDisabled();
		}
		
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
				case PH:
					contPhonon.loadProjectParameters();addRightPane(scrollPhonon,enumStepArray[i]);
					break;
				case BANDS:
					contBands.loadProjectParameters();addRightPane(scrollBands,enumStepArray[i]);
					break;
				case BANDSPP:
					addRightPane(scrollBandsPP,enumStepArray[i]);
					break;
				case NEB:
					contNeb.loadProjectParameters();addRightPane(scrollNeb,enumStepArray[i]);
					break;
				default:ShowAlert.showAlert(AlertType.INFORMATION, "Error", 
						"Nonimplemented controller: "+(enumStepArray[i]==null?"null":enumStepArray[i].toString()));break;
			}
		}

		try {tabPaneRight.getSelectionModel().select(1);}catch (Exception e) {}//load second tab(not geo)
		
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
	private void releaseHboxOutputContent() {
		for(Tab tb:projectTabDict.values()) {
			if(tb.getContent()==splitOutput) {tb.setContent(null);}
		}
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
	private void chooseInitialDir(DirectoryChooser dirChooser, String pathNow) {
		if(pathNow==null || pathNow.isEmpty() || !(new File(pathNow)).canRead()) {
			String currentPath = Paths.get(".").toAbsolutePath().normalize().toString();
			File tmpFile = new File(currentPath);
			if(tmpFile.canRead()) {
				dirChooser.setInitialDirectory(tmpFile);
			}
		}
		else {
			dirChooser.setInitialDirectory(new File(pathNow));
		}
	}
}
