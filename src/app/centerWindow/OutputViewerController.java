/*******************************************************************************
 * Copyright (c) 2020 Haonan Huang.
 *
 *     This file is part of QuantumVITAS (Quantum Visualization Interactive 
 *     Toolkit for Ab-initio Simulations).
 *
 *     QuantumVITAS is free software: you can redistribute it and/or modify
 *     it under the terms of the GNU General Public License as published by
 *     the Free Software Foundation, either version 3 of the License, or any 
 *     later version.
 *
 *     QuantumVITAS is distributed in the hope that it will be useful,
 *     but WITHOUT ANY WARRANTY; without even the implied warranty of
 *     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *     GNU General Public License for more details.
 *
 *     You should have received a copy of the GNU General Public License
 *     along with QuantumVITAS.  If not, see <https://www.gnu.org/licenses/gpl-3.0.txt>.
 *******************************************************************************/
package app.centerWindow;

import java.awt.Desktop;
import java.io.File;
import java.io.IOException;
import java.net.URL;
import java.util.ArrayList;
import java.util.List;
import java.util.ResourceBundle;
import java.util.Scanner;
import java.util.stream.Collectors;
import java.util.stream.Stream;

import com.consts.Constants.EnumAnalysis;
import com.consts.Constants.EnumCard;
import com.consts.Constants.EnumFileCategory;
import com.consts.Constants.EnumNameList;
import com.programconst.DefaultFileNames;
import com.programconst.ProgrammingConsts;

import javafx.fxml.FXML;
import javafx.fxml.Initializable;
import javafx.scene.control.Button;
import javafx.scene.control.ComboBox;
import javafx.scene.control.Label;
import javafx.scene.control.ListCell;
import javafx.scene.control.ListView;
import javafx.scene.control.ScrollPane;
import javafx.scene.layout.HBox;
import javafx.scene.layout.VBox;
import javafx.scene.paint.Color;
import javafx.scene.text.Text;
import javafx.scene.text.TextFlow;
import javafx.util.Callback;
import main.MainClass;

public class OutputViewerController implements Initializable{

    @FXML private HBox rootHbox;

    @FXML private VBox vBoxCalcFolder,vboxFiles,vboxMainPlot;

    @FXML private ListView<String> listCalcFolders;

    @FXML private ListView<String> listFiles;
    
    @FXML private ScrollPane displayScroll;
    
    @FXML private Button deleteFolderButton,deleteFileButton,openAsButton,buttonRefreshFolder,buttonRefreshFiles;
    
    @FXML private Label labelFileCategory;
    
    @FXML private ComboBox<EnumAnalysis> comboAnalysis;
    
    private TextFlow textFlowDisplay;
    
    private MainClass mainClass;
    
    private File calcFolder;
    
    private File inoutFiles;
    
    private EnumFileCategory fileCategory;
    
    private FileDataClass fileData;
    
    public OutputViewerController(MainClass mc) {
    	mainClass = mc;
    	textFlowDisplay = new TextFlow();
    	fileData = new FileDataClass();
	}

	@Override
	public void initialize(URL arg0, ResourceBundle arg1) {
		
		listCalcFolders.getSelectionModel().selectedItemProperty().addListener((ov, oldTab, newTab) -> {
			if(newTab==null || newTab.isEmpty()) return;
			File pjFolder = getProjectFolder();
			if(pjFolder==null || !pjFolder.canRead()) return;
			calcFolder = new File(pjFolder,newTab);
			
			updateFilesInCalcFolder();
		});
		listFiles.getSelectionModel().selectedItemProperty().addListener((ov, oldTab, newTab) -> {
			fileCategory = null;
			labelFileCategory.setText("");
			EnumAnalysis analTmp = comboAnalysis.getSelectionModel().getSelectedItem();//cache the selected item before clearing
			comboAnalysis.getItems().clear();
			
			if(newTab==null || newTab.isEmpty()) return;
			if(calcFolder==null || !calcFolder.canRead() || !calcFolder.isDirectory()) return;
			inoutFiles = new File(calcFolder,newTab);
			if(!inoutFiles.canRead()) return;
			
			if(newTab.contains(ProgrammingConsts.stdinExtension)) {fileCategory = EnumFileCategory.stdin;}
			else if(newTab.contains(ProgrammingConsts.stdoutExtension)) {fileCategory = EnumFileCategory.stdout;}
			else if(newTab.contains(ProgrammingConsts.stderrExtension)) {fileCategory = EnumFileCategory.stderr;}
			else if(newTab.contains(DefaultFileNames.calcSaveFile)||newTab.contains(DefaultFileNames.projSaveFile)) 
			{fileCategory = EnumFileCategory.save;}
			else if(newTab.contains(".xml")) {fileCategory = EnumFileCategory.xmlout;}
			else if(newTab.toLowerCase().contains("crash")) {fileCategory = EnumFileCategory.crash;}
			else if(inoutFiles.isDirectory()) {fileCategory = EnumFileCategory.directory;}
			else {fileCategory = EnumFileCategory.unknown;}
			
			if(fileCategory!=null) {labelFileCategory.setText(fileCategory.toString());}//should not be null until this point!
			
			if(fileCategory!=null) {
				comboAnalysis.getItems().addAll(EnumAnalysis.info);//always has the option of show summarized info
				comboAnalysis.getItems().addAll(EnumAnalysis.text);//always has the option of show in text
				
				if(analTmp!=null && comboAnalysis.getItems()!=null && comboAnalysis.getItems().contains(analTmp)) {
					//select back the choice before
					comboAnalysis.getSelectionModel().select(analTmp);
				}
				else {
					//select text first if there has been no selection
					comboAnalysis.getSelectionModel().select(EnumAnalysis.text);
				}
			}
			updateIoDisplay();//*** not efficient because runs twice
		});
		comboAnalysis.getSelectionModel().selectedItemProperty().addListener((ov, oldTab, newTab) -> {
			updateIoDisplay();
		});
		openAsButton.setOnAction((event) -> {
			if(inoutFiles==null || !inoutFiles.canRead()) return;
			try {
				Desktop.getDesktop().open(inoutFiles);
			} catch (IOException e) {
				// TODO Auto-generated catch block
				e.printStackTrace();
			}
		});
		buttonRefreshFolder.setOnAction((event) -> {
			int tmpInt = listCalcFolders.getSelectionModel().getSelectedIndex();
			updateProjectFolder();
			if(tmpInt>=0 && listCalcFolders.getItems()!=null && listCalcFolders.getItems().size()>tmpInt) {
				listCalcFolders.getSelectionModel().select(tmpInt);
			}
		});
		buttonRefreshFiles.setOnAction((event) -> {
			updateFilesInCalcFolder();
		});
		deleteFolderButton.setOnAction((event) -> {
			try {
				deleteDirectory(calcFolder);
			} catch (IOException e) {
				e.printStackTrace();
			}
			updateProjectFolder();
		});
		deleteFileButton.setOnAction((event) -> {
			try {
				deleteDirectory(inoutFiles);
			} catch (IOException e) {
				e.printStackTrace();
			}
			updateFilesInCalcFolder();
		});
		
	}
	boolean deleteDirectory(File directoryToBeDeleted) throws IOException {
	    File[] contentFiles = directoryToBeDeleted.listFiles();
	    if (contentFiles != null) {
	        for (File file : contentFiles) {
	            deleteDirectory(file);
	        }
	    }
	    return directoryToBeDeleted.delete();
	}
	private void updateFilesInCalcFolder() {
		int tmpInt = listFiles.getSelectionModel().getSelectedIndex();
		
		listFiles.getItems().clear();
		
		if(calcFolder==null || !calcFolder.canRead() || !calcFolder.isDirectory()) return;
		
		File[] fileList = calcFolder.listFiles();
		for (File f : fileList) {
			listFiles.getItems().add(f.getName());
		}
		
		if(tmpInt>=0 && listFiles.getItems()!=null && listFiles.getItems().size()>tmpInt) {
			listFiles.getSelectionModel().select(tmpInt);//will invoke selection change listener and update "inoutFiles"
		}
	}
	private void updateIoDisplay() {
		EnumAnalysis analTmp = comboAnalysis.getSelectionModel().getSelectedItem();
		
		displayScroll.setContent(null);
		if(fileCategory==null || analTmp==null) return;
		
		if(analTmp.equals(EnumAnalysis.text)) {//show raw text
			displayScroll.setContent(textFlowDisplay);
			readTextFileToTextFlow();//only highlight input files
		}
		else if(analTmp.equals(EnumAnalysis.info)) {//show summarized information
			displayScroll.setContent(textFlowDisplay);
			textFlowDisplay.getChildren().clear();
			if(fileCategory.equals(EnumFileCategory.stdout)) {
				if(!summarizeInfoStdOut()) {return;}
				textFlowDisplay.getChildren().add(new Text(fileData.toString()));
			}
			else {
				textFlowDisplay.getChildren().add(new Text("The information summary is not available for this file type."));
			}
		}
	}
	private boolean summarizeInfoStdOut() {//return false when error
		String strTmp1 = checkErrors();
		if(strTmp1!=null && !strTmp1.isEmpty()) {return false;}
		fileData.clearAll();
		try {
		    Scanner sc = new Scanner(inoutFiles); 
		  
		    String strTmp;
		    
		    int lineCount=0;
		    while (sc.hasNextLine()) {
		    	lineCount++;
		    	strTmp = sc.nextLine();
		    	//total energy
		    	if(strTmp==null || strTmp.isEmpty()) continue;
		    	
		    	String lowerCaseStr = strTmp.toLowerCase();
		    	if(lowerCaseStr.contains("nstep")&& strTmp.contains("=")) {
		    		String[] splitted = strTmp.trim().split("\\s+");//split the string by whitespaces
		    		try {
		    			Integer dbTmp =  Integer.valueOf(splitted[2]);
		    			if(dbTmp!=null) {fileData.nstep = dbTmp;}
		    		}catch(Exception e) {
		    			e.printStackTrace();
		    		}
		    	}
		    	if(lowerCaseStr.contains("total energy") && strTmp.contains("=")) {
		    		String[] splitted = strTmp.trim().split("\\s+");//split the string by whitespaces
		    		try {
		    			if(strTmp.contains("!")) {
			    			Double dbTmp =  Double.valueOf(splitted[4]);
			    			if(dbTmp!=null) {fileData.addTotalEnergy(dbTmp, true);}
		    			}
		    			else {
		    				Double dbTmp =  Double.valueOf(splitted[3]);
			    			if(dbTmp!=null) {fileData.addTotalEnergy(dbTmp, false);}
		    			}
		    		}catch(Exception e) {
		    			e.printStackTrace();
		    		}
		    	}
		    	if(lowerCaseStr.contains("total magnetization") && strTmp.contains("=")) {
		    		String[] splitted = strTmp.trim().split("\\s+");//split the string by whitespaces
		    		try {
		    			Double dbTmp =  Double.valueOf(splitted[3]);
		    			if(dbTmp!=null) {fileData.addMag(dbTmp, true);}
		    		}catch(Exception e) {
		    			e.printStackTrace();
		    		}
		    	}
		    	if(lowerCaseStr.contains("absolute magnetization") && strTmp.contains("=")) {
		    		String[] splitted = strTmp.trim().split("\\s+");//split the string by whitespaces
		    		try {
		    			Double dbTmp =  Double.valueOf(splitted[3]);
		    			if(dbTmp!=null) {fileData.addMag(dbTmp, false);}
		    		}catch(Exception e) {
		    			e.printStackTrace();
		    		}
		    	}
		    	//highest occupied level
		    	if(lowerCaseStr.contains("highest occupied level")) {
		    		String[] splitted = strTmp.trim().split("\\s+");//split the string by whitespaces
		    		try {
		    			Double dbTmp =  Double.valueOf(splitted[4]);
		    			if(dbTmp!=null) {fileData.setHomo(dbTmp);}
		    		}catch(Exception e) {
		    			e.printStackTrace();
		    		}
		    	}
				if(lowerCaseStr.contains("fermi energy")) {
					String[] splitted = strTmp.trim().split("\\s+");//split the string by whitespaces
					try {
		    			Double dbTmp =  Double.valueOf(splitted[4]);
		    			if(dbTmp!=null) {fileData.setFermi(dbTmp);}
		    		}catch(Exception e) {
		    			e.printStackTrace();
		    		}
				}
				if(lowerCaseStr.contains("self-consistent calculation")) {
					fileData.hasScf = true;
					if(strTmp.toLowerCase().contains("end of")) {fileData.hasScfFinished=true;}
				}
				if(lowerCaseStr.contains("molecular dynamics calculation")) {
					fileData.isMD = true;
					if(strTmp.toLowerCase().contains("end of")) {fileData.isMDFinished=true;}
				}
				if(lowerCaseStr.contains("geometry optimization")) {
					fileData.isOpt = true;
					if(strTmp.toLowerCase().contains("end of")) {fileData.isOptFinished=true;}
				}
				if(lowerCaseStr.contains("band structure calculation")) {
					fileData.isNscf = true;
					if(strTmp.toLowerCase().contains("end of")) {fileData.isNscfFinished=true;}
				}
				
				if(strTmp.toUpperCase().contains("JOB DONE")) {
					fileData.isJobDone = true;
				}
		    }
		    
		    sc.close();
		    
		    if(lineCount==0) {
		    	textFlowDisplay.getChildren().add(new Text("No lines detected. File empty or binary file."));
		    }
		} catch (IOException e) {
			e.printStackTrace();
			return false;
		}
		return true;
	}
	private String checkErrors() {
		if(fileCategory==null) {return "Error: file category is null. Check code!";}
		if(fileCategory.equals(EnumFileCategory.directory)) {return "Target file is a directory.";}
		if(inoutFiles==null || !inoutFiles.canRead()) {return "Error: cannot read file.";}
		return "";
	}
	private void readTextFileToTextFlow() {
		textFlowDisplay.getChildren().clear();
		String strTmp1 = checkErrors();
		if(strTmp1!=null && !strTmp1.isEmpty()) {textFlowDisplay.getChildren().add(new Text(strTmp1));return;}
		
		boolean boolHighLight = false;
		if(fileCategory.equals(EnumFileCategory.stdin)) {boolHighLight=true;}
		
		try {
//			String data = new String(Files.readAllBytes(inoutFiles.toPath()));
//			textFlowDisplay.getChildren().add(new Text(data));
		    Scanner sc = new Scanner(inoutFiles); 
		  
		    String strTmp;
		    Text txtTmp;
		    int lineCount=0;
		    while (sc.hasNextLine()) {
		    	lineCount++;
		    	strTmp = sc.nextLine();
		    	txtTmp = new Text(strTmp+"\n");
		    	if(boolHighLight) {
			    	if(strTmp!=null && strTmp.contains("calculation")&& strTmp.contains("=")) {txtTmp.setFill(Color.BLUE);}
			    	if(strTmp!=null && containsSectionName(strTmp) && !strTmp.contains("=")) {txtTmp.setFill(Color.GREEN);}
		    	}
		    	textFlowDisplay.getChildren().add(txtTmp);
		    }
		    
		    sc.close();
		    
		    if(lineCount==0) {
		    	textFlowDisplay.getChildren().add(new Text("No lines detected. File empty or binary file."));
		    }
		} catch (IOException e) {
			e.printStackTrace();
		} 
	}
	private boolean containsSectionName(String stTmp) {
		if(stTmp==null || stTmp.isEmpty()) return false;
		String newstTmp = stTmp.replaceAll("\\s+","").toLowerCase();//remove all whitespaces and to lower case
		List<String> enumValues1 = Stream.of(EnumNameList.values())
                .map(EnumNameList::toString)
                .collect(Collectors.toList());
		List<String> enumValues2 = Stream.of(EnumCard.values())
                .map(EnumCard::toString)
                .collect(Collectors.toList());
		for (String st : enumValues1) {
			if(newstTmp.contains(st.trim().toLowerCase())) {return true;}
		}
		for (String st : enumValues2) {
			if(newstTmp.contains(st.trim().toLowerCase())) {return true;}
		}
		return false;
		
	}
	private File getProjectFolder() {
		String wsp = mainClass.projectManager.workSpacePath;
		String pj = mainClass.projectManager.getActiveProjectName();
		if(wsp==null || pj==null || pj.isEmpty()) return null;
		return new File(new File(wsp),pj);
	}
	public void updateProjectFolder() {
		listCalcFolders.getItems().clear();listFiles.getItems().clear();
		
		File pjFolder = getProjectFolder();
		if(pjFolder==null || !pjFolder.canRead()) return;
		
		File[] fileList = pjFolder.listFiles();
		int count = 0;
		for (File f : fileList) {
			if(f.isDirectory()) {listCalcFolders.getItems().add(f.getName());count++;}
		}
		ArrayList<String> pureFiles = new ArrayList<String>();
		for (File f : fileList) {
			if(f.isFile()) {listCalcFolders.getItems().add(f.getName());pureFiles.add(f.getName());}
		}
		if(count>0) {listCalcFolders.getSelectionModel().select(0);}//will invoke selection change listener and update "calcFolder"
		listCalcFolders.setCellFactory(new Callback<ListView<String>, ListCell<String>>() {
	        @Override 
	        public ListCell<String> call(ListView<String> param) {
	            return new ListCell<String>() {
	                @Override 
	                protected void updateItem(String item, boolean empty) {
	                    super.updateItem(item, empty);
	                    if (pureFiles.contains(item)) {
	                        setDisable(true);setTextFill(Color.LIGHTGRAY);
	                    } else {
	                        setDisable(false);setTextFill(Color.BLACK);
	                    }
	                    setText(item);
	                }

	            };
	        }
	    });
		
	}


}
