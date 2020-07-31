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
import java.net.URL;
import java.util.HashMap;
import java.util.Iterator;
import java.util.Map;
import java.util.Map.Entry;
import java.util.ResourceBundle;

import javafx.fxml.FXML;
import javafx.fxml.Initializable;
import javafx.scene.control.Alert;
import javafx.scene.control.Button;
import javafx.scene.control.MenuButton;
import javafx.scene.control.MenuItem;
import javafx.scene.control.TreeItem;
import javafx.scene.control.TreeTableColumn;
import javafx.scene.control.TreeTableView;
import javafx.scene.control.Alert.AlertType;
import javafx.scene.control.cell.TreeItemPropertyValueFactory;
import javafx.scene.text.Font;
import javafx.scene.text.FontWeight;
import main.MainClass;
import com.consts.Constants.EnumCalc;
import com.error.ShowAlert;

import project.ProjectCalcLog;

public class MainLeftPaneController implements Initializable {
	
	@FXML public TreeTableView<ProjectCalcLog> projectTree;
	@FXML public Button buttonOpenSelected,
	buttonRefresh,
	createProject;
	@FXML public MenuButton calcMain;
	@FXML public MenuItem calcScf,
	calcOpt,
	calcDos,
    calcBands,
    calcMd,
    calcTddft,
    calcPhonon,
    calcCustom;
	
	private TreeItem<ProjectCalcLog> projectTreeRoot;
	private MainClass mainClass;
	private HashMap<String, TreeItem<ProjectCalcLog>> projectTreeDict;
	private HashMap<String, HashMap<String, TreeItem<ProjectCalcLog>>> projectCalcTreeDict;
	
    public MainLeftPaneController(MainClass mc) {
    	mainClass = mc;
    }

	@Override
	public void initialize(URL arg0, ResourceBundle arg1) {
		initialize();
	}
	public void initialize() {
		projectTreeDict = new HashMap<String, TreeItem<ProjectCalcLog>> ();
		projectCalcTreeDict = new HashMap<String, HashMap<String, TreeItem<ProjectCalcLog>>>();
		
		TreeTableColumn<ProjectCalcLog, String> treeTableColumn1 = new TreeTableColumn<>("Project");
		TreeTableColumn<ProjectCalcLog, String> treeTableColumn2 = new TreeTableColumn<>("Calc. Name");
		TreeTableColumn<ProjectCalcLog, String> treeTableColumn3 = new TreeTableColumn<>("Calc. Type");
		TreeTableColumn<ProjectCalcLog, String> treeTableColumn4 = new TreeTableColumn<>("Status");
		
		treeTableColumn1.setPrefWidth(110);
		treeTableColumn2.setPrefWidth(85);
		treeTableColumn3.setPrefWidth(82);
		treeTableColumn4.setPrefWidth(70);
		
		treeTableColumn1.setCellValueFactory(new TreeItemPropertyValueFactory<>("project"));
		treeTableColumn2.setCellValueFactory(new TreeItemPropertyValueFactory<>("calculation"));
		treeTableColumn3.setCellValueFactory(new TreeItemPropertyValueFactory<>("calcType"));
		treeTableColumn4.setCellValueFactory(new TreeItemPropertyValueFactory<>("status"));

		projectTree.getColumns().add(treeTableColumn1);
		projectTree.getColumns().add(treeTableColumn2);
		projectTree.getColumns().add(treeTableColumn3);
		projectTree.getColumns().add(treeTableColumn4);
		
		//projectTreeDict = new HashMap<String, TreeItem<String>>();
		//projectCalcTreeDict = new HashMap<String, HashMap<EnumCalc, TreeItem<String>>>();
//		projectTreeDict = new HashMap<String, TreeItem<ProjectCalcLog>>();
//		projectCalcTreeDict = new HashMap<String, HashMap<EnumCalc, TreeItem<ProjectCalcLog>>>();
				
		
		
		projectTree.getSelectionModel().selectedItemProperty().addListener((v, oldValue, newValue) -> { 
			if(newValue==null || projectTreeRoot==null) return;
			else {
				while(newValue!=null && !projectTreeRoot.getChildren().contains(newValue)) {
					newValue=newValue.getParent();//go back up until the children of the root
				}
				if(newValue==null) return;
				String pj = newValue.getValue().getProject();
				setOpenCloseButtons(!mainClass.projectManager.containsProject(pj));
			}
		});
		buttonRefresh.setOnAction((event) -> {
			updateProjects(true);
		});
		
		projectTreeRoot = new TreeItem<ProjectCalcLog>(new ProjectCalcLog("Workspace","","",""));
		projectTree.setRoot(projectTreeRoot);
		projectTreeRoot.setExpanded(true);
	}
	public void setOpenCloseButtons(boolean bl) {
		//true -> can open
		//false -> already open
		if(bl) {
			buttonOpenSelected.setFont(Font.font(buttonOpenSelected.getFont().toString(), FontWeight.BOLD, buttonOpenSelected.getFont().getSize()));
			buttonOpenSelected.setDisable(false);
		}
		else {
			buttonOpenSelected.setFont(Font.font(buttonOpenSelected.getFont().toString(), FontWeight.NORMAL, buttonOpenSelected.getFont().getSize()));
			buttonOpenSelected.setDisable(true);
		}
	}
	public String getSelectedProject() {
		TreeItem<ProjectCalcLog> ti = projectTree.getSelectionModel().getSelectedItem();
		if(ti==null || projectTreeRoot==null) return null;
		else {
			//checking ti!=null will increase program rigidity, but not necessary
			while(ti!=null && !projectTreeRoot.getChildren().contains(ti)) {
				ti=ti.getParent();//go back up until the children of the root
			}
			if(ti==null) return null;
			return ti.getValue().getProject();
		}
		
	}
	public void selectProj(String projName) {
		if(projName==null || projectTreeDict.get(projName)==null) {return;}
		projectTree.getSelectionModel().select(projectTreeDict.get(projName));
	}
	public void selectCalc(String projName, String calcName) {
		if(projName==null || calcName==null || projectTreeDict.get(projName)==null || projectCalcTreeDict.get(projName)==null) {
			ShowAlert.showAlert(AlertType.INFORMATION, "Error", "No item for the project found in the TreeView.");
			return;}
		projectTreeDict.get(projName).setExpanded(true);
		for (TreeItem<ProjectCalcLog> value : projectCalcTreeDict.get(projName).values()) {
			if(calcName.equals(value.getValue().getCalculation())) {
				projectTree.getSelectionModel().select(value);
				return;
			}
		}
		ShowAlert.showAlert(AlertType.INFORMATION, "Error", "Cannot find calculation "+calcName+" under project "+projName+" in the TreeView.");
	}
	public void closeProject(String pj) {
		if(projectCalcTreeDict.get(pj)==null) {return;}
		
		for (TreeItem<ProjectCalcLog> value : projectCalcTreeDict.get(pj).values()) {
			value.getParent().getChildren().remove(value);
		}
		projectCalcTreeDict.get(pj).clear();
		
		File wsDir = mainClass.projectManager.getWorkSpaceDir();

		if (wsDir==null || !wsDir.canRead()) {
			return;
		}
		
		if(!(new File(wsDir,pj)).exists()) {
			//also remove the project from the treeview if not saved
			removeProject(pj);
		}
	}
	public void addProject(String pj) {
		TreeItem<ProjectCalcLog> ti = new TreeItem<ProjectCalcLog>(new ProjectCalcLog(pj,"Geometry","",""));
		projectTreeRoot.getChildren().add(ti);
		projectTreeRoot.setExpanded(true);
		projectTreeDict.put(pj,ti);
		projectCalcTreeDict.put(pj, new HashMap<String, TreeItem<ProjectCalcLog>>());
	}
	public void updateCalcTree(String ec) {
		String currentProject = mainClass.projectManager.getActiveProjectName();
		if (currentProject!=null && projectTreeDict.containsKey(currentProject) && projectCalcTreeDict.containsKey(currentProject)) {
			if (ec==null || ec.isEmpty()) {
				return;
			}
			if (!projectCalcTreeDict.get(currentProject).containsKey(ec)) {
				//add tree item if not already exists
				EnumCalc ecType = mainClass.projectManager.getActiveProject().getCalcType(ec);
				TreeItem<ProjectCalcLog> ti;
				if(ecType==null) {ti = new TreeItem<ProjectCalcLog>(new ProjectCalcLog("",ec,"",""));}
				else {ti = new TreeItem<ProjectCalcLog>(new ProjectCalcLog("",ec,ecType.getShort(),""));}
				
				projectCalcTreeDict.get(currentProject).put(ec, ti);
				projectTreeDict.get(currentProject).getChildren().add(ti);
				//expand project tree, select active calc item
				projectTreeDict.get(currentProject).setExpanded(true);
				//int row = projectTree.getRow(ti);
				//projectTree.getSelectionModel().select(row);
				
				//select the newly created treeitem
				projectTree.getSelectionModel().select(ti);
			}
			else {
				//expand project tree, select active calc item
				projectTreeDict.get(currentProject).setExpanded(true);
				int row = projectTree.getRow(projectCalcTreeDict.get(currentProject).get(ec));
				projectTree.getSelectionModel().select(row);
			}
			
		}
	}
	public void updateFullCalcTree() {
		for(String ec : mainClass.projectManager.getCurrentCalcList()) {
			updateCalcTree(ec);
		}
	}
	public void updateCalcTree() {
		if (mainClass.projectManager.existCurrentCalc()) {
			updateCalcTree(mainClass.projectManager.getCurrentCalcName());
		}
	}
	public void clearTree() {
		projectTreeRoot.getChildren().clear();
		projectTreeDict.clear();
		projectCalcTreeDict.clear();
	}
	private void removeProject(String pj) {
	    projectTreeRoot.getChildren().remove(projectTreeDict.get(pj));
	    projectTreeDict.remove(pj);
		projectCalcTreeDict.remove(pj);
	}
	public void updateProjects(boolean boolShowAlert) {
		File wsDir = mainClass.projectManager.getWorkSpaceDir();

		if (wsDir==null || !wsDir.canRead()) {
			if(boolShowAlert) {
				Alert alert1 = new Alert(AlertType.ERROR);
		    	alert1.setTitle("Error");
		    	alert1.setContentText("The workspace folder is not available! Please check before continuing!");
		    	alert1.showAndWait();
	    	}
			return;
		}
		
		File[] directories = wsDir.listFiles(File::isDirectory);
		//remove projects that no longer has a folder and is not opened in the program now
		//need to use iterator rather than projectTreeDict.keySet(), otherwise ConcurrentModificationException
		Iterator<Entry<String, TreeItem<ProjectCalcLog>>> it = projectTreeDict.entrySet().iterator();
	    while (it.hasNext()) {
	        Map.Entry<String, TreeItem<ProjectCalcLog>> pair = (Map.Entry<String, TreeItem<ProjectCalcLog>>)it.next();
	        String keyStr = pair.getKey();//pair.getValue()
	        boolean flagExist = false;
			for (File temp : directories) {
				String tmp = temp.getName();
				if(tmp!=null && tmp.equals(keyStr)) {flagExist=true;break;}
			}
			if(!flagExist && !mainClass.projectManager.existProject(keyStr)) {//not exist a folder nor opened in the program
				projectTreeRoot.getChildren().remove(pair.getValue());
				projectCalcTreeDict.remove(keyStr);
				it.remove();//projectTreeDict.remove(keyStr);
			}
			
	        
	    }

		//add newly detected
		for (File temp : directories) {
			String tmp = temp.getName();
			if(!projectTreeDict.containsKey(tmp)) {
				TreeItem<ProjectCalcLog> ti = new TreeItem<ProjectCalcLog>(new ProjectCalcLog(tmp,"Geometry","",""));
				projectTreeRoot.getChildren().add(ti);
				projectTreeRoot.setExpanded(true);
				projectTreeDict.put(tmp,ti);
				projectCalcTreeDict.put(tmp, new HashMap<String, TreeItem<ProjectCalcLog>>());
			}	
		}
		
	}
}
