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
package core.app.centerwindow;

import java.awt.Desktop;
import java.awt.Desktop.Action;
import java.io.File;
import java.io.IOException;
import java.net.URL;
import java.util.ArrayList;
import java.util.Objects;
import java.util.ResourceBundle;
import javafx.beans.binding.Bindings;
import javafx.collections.FXCollections;
import javafx.collections.ObservableList;
import javafx.fxml.FXML;
import javafx.fxml.Initializable;
import javafx.scene.chart.LineChart;
import javafx.scene.chart.NumberAxis;
import javafx.scene.chart.XYChart.Data;
import javafx.scene.chart.XYChart.Series;
import javafx.scene.control.Button;
import javafx.scene.control.ComboBox;
import javafx.scene.control.Label;
import javafx.scene.control.ListCell;
import javafx.scene.control.ListView;
import javafx.scene.control.ScrollPane;
import javafx.scene.control.SplitPane;
import javafx.scene.control.TextField;
import javafx.scene.control.ToggleButton;
import javafx.scene.layout.HBox;
import javafx.scene.layout.VBox;
import javafx.scene.text.TextFlow;
import javafx.util.Callback;
import javafx.util.StringConverter;
import javafx.util.converter.NumberStringConverter;

import com.consts.Constants.EnumAnalysis;
import com.consts.Constants.EnumFileCategory;

import app.centerwindow.FileDataClass;
import core.app.input.InputGeoController;
import core.com.error.ShowAlert;
import core.main.MainClass;

public abstract class OutputViewerController implements Initializable{

@FXML private SplitPane rootSplitPane;
	
    @FXML protected VBox vboxFiles,
    vboxMainPlot;

    @FXML protected ListView<String> listFiles;
    
    @FXML protected ScrollPane displayScroll;
    
    @FXML protected Button deleteFileButton,
    openAsButton,
    buttonRefreshFiles,
    buttonRefresh,
    buttonSaveGeo,
	buttonShowInSystem;
    
    @FXML protected ToggleButton toggleAutoRange,
    toggleShiftFermi;
    
    @FXML protected TextField textXlimLow,
    textXlimHigh,
    textYlimLow,
    textYlimHigh;
    
    @FXML protected Label labelFileCategory,//yes
    labelPlot,
    labelK;
    
    @FXML protected ComboBox<EnumAnalysis> comboAnalysis;//yes
    
    @FXML protected ComboBox<String> comboPlot,
    comboHighSymK;
    
    @FXML protected HBox hboxPlotToolbar,
    hboxBandsToolbar;
    
    @FXML protected ToggleButton buttonShowMarker,
    toggleLegend,
    toggleElementOrAtom;
    
    @FXML protected TextField textMarkerScale;
    
	protected MainClass mainClass;//yes
	
	protected InputGeoController contGeo;//yes
	
	protected TextFlow textFlowDisplay;//yes
    
	protected File calcFolder;//yes
    
	protected File inoutFiles;//yes
    
	protected EnumFileCategory fileCategory;//yes
    
	protected FileDataClass fileData;//yes
    
	protected NumberAxis xAxis;//yes

	protected NumberAxis yAxis;//yes

	protected LineChart<Double, Double> lineChart;//yes
    
	protected WorkScene3D geometry3d;//yes
    
	protected double minY,
	maxY,
	minX,
	maxX;
    
	public OutputViewerController(MainClass mc, InputGeoController cg) {
    	mainClass = mc;
    	contGeo = cg;
    	
    	textFlowDisplay = new TextFlow();
    	fileData = new FileDataClass();
    	xAxis = new NumberAxis();xAxis.setAutoRanging(true);xAxis.setForceZeroInRange(false);
    	yAxis = new NumberAxis();yAxis.setAutoRanging(true);yAxis.setForceZeroInRange(false);
    	
    	geometry3d = new WorkScene3D();
    	geometry3d.addAnimate3D(fileData);//add animation panel and link the data file
    	geometry3d.buildGeometry(fileData.getGeoAgent());//link the geoAgent in fileData to the workscene3d plot

    	lineChart = new LineChart(xAxis, yAxis);
	}
	
	@Override
	public void initialize(URL arg0, ResourceBundle arg1) {
		geometry3d.centerSubScene(displayScroll);
		
		lineChart.prefWidthProperty().bind(displayScroll.widthProperty());
		lineChart.prefHeightProperty().bind(displayScroll.heightProperty());
		lineChart.setCreateSymbols(false);
		lineChart.setAnimated(false);
		lineChart.setLegendVisible(true);
		
		//lineChart.prefHeightProperty().bind(workSpaceTabPane.heightProperty());
		
		listFiles.setCellFactory(new Callback<ListView<String>, ListCell<String>>() {
	        @Override 
	        public ListCell<String> call(ListView<String> param) {
	            return new ListCell<String>() {
	                @Override 
	                protected void updateItem(String item, boolean empty) {
	                    super.updateItem(item, empty);
	                    if (item==null) {
	                    	setStyle("-fx-font-weight: normal; "
	                    			+"-fx-border-color: white; ");
	                    	setText(item);
	                    }
	                    else {
	                    	if (isFileImportant(item)) {
	                        	setStyle("-fx-font-weight: bolder; "
	                        			+"-fx-border-color: green; ");
	                        } else {
	                        	setStyle("-fx-font-weight: normal; "
	                        			+"-fx-border-color: white; ");
	                        }
		                    setText(item);
	                    }
	                }

	            };
	        }
		});
		listFiles.getSelectionModel().selectedItemProperty().addListener((ov, oldTab, newTab) -> {
			//ShowAlert.showAlert(AlertType.INFORMATION, "Debug", "listFiles: "+oldTab + "," + newTab);
			//final int comboAnalysisSelect = comboAnalysis.getSelectionModel().getSelectedIndex();
			
			fileCategory = null;
			fileData.clearAll();buttonSaveGeo.setDisable(true);
			labelFileCategory.setText("");
//			EnumAnalysis analTmp = comboAnalysis.getSelectionModel().getSelectedItem();//cache the selected item before clearing
			comboAnalysis.getItems().clear();//do not change this, because this ensures that this will trigger the selection listener of comboAnalysis
			
			if(newTab==null || newTab.isEmpty()) return;
			if(calcFolder==null || !calcFolder.canRead() || !calcFolder.isDirectory()) return;
			inoutFiles = new File(calcFolder,newTab);
			if(!inoutFiles.canRead()) return;
			
			getFileCategory(newTab);
			
			fileData.fileCategory = fileCategory;
			
			if(fileCategory!=null) {labelFileCategory.setText(fileCategory.toString());}//should not be null until this point!
			
			loadFile();
			
			updateComboAnalysis();
			
		});
		buttonRefresh.setOnAction((event) -> {
			if((fileData.isMD || fileData.isOpt) && !comboAnalysis.getItems().contains(EnumAnalysis.plot3D)) {comboAnalysis.getItems().addAll(EnumAnalysis.plot3D);}
			loadFile();
			updateIoDisplay();
			//ShowAlert.showAlert(AlertType.INFORMATION, "Debug", "updateIoDisplay involked by buttonRefresh.", false);
		});
		comboAnalysis.getSelectionModel().selectedItemProperty().addListener((ov, oldTab, newTab) -> {
			if(newTab!=null) {//very crucial to check null here!
				updateIoDisplay();
				//ShowAlert.showAlert(AlertType.INFORMATION, "Debug", "updateIoDisplay involked by comboAnalysis.", false);
			}
		});
		comboPlot.getSelectionModel().selectedItemProperty().addListener((ov, oldTab, newTab) -> {
			if(newTab!=null) {//very crucial to check null here!
				if(oldTab!=null) {//better efficiency, since only user made changes will be carried out (selection after clear will not do anything)
					updateIoDisplay();
					//ShowAlert.showAlert(AlertType.INFORMATION, "Debug", "updateIoDisplay involked by comboPlot.", false);
				}
			}
		});
		openAsButton.setOnAction((event) -> {
			if(inoutFiles==null || !inoutFiles.canRead()) return;
			
			if( Desktop.isDesktopSupported() && Desktop.getDesktop().isSupported(Action.OPEN))
			{
			    new Thread(() -> {
				   try {
				       Desktop.getDesktop().open(inoutFiles);
				   } catch (IOException e1) {
				       e1.printStackTrace();
				   }
			       }).start();
			}
			else {
				ShowAlert.showAlert("Information", "Opening files externally not supported in the current operating system.");
			}
		});
		buttonShowInSystem.setOnAction((event) -> {
			if(calcFolder==null || !calcFolder.canRead() || !calcFolder.isDirectory()) return;
			if( Desktop.isDesktopSupported()  && Desktop.getDesktop().isSupported(Action.OPEN))
			{
			    new Thread(() -> {
				   try {
				       Desktop.getDesktop().open(calcFolder);
				   } catch (IOException e1) {
				       e1.printStackTrace();
				   }
			       }).start();
			}
			else {
				ShowAlert.showAlert("Information", "Opening files externally not supported in the current operating system.");
			}
		});
		buttonShowMarker.selectedProperty().bindBidirectional(lineChart.createSymbolsProperty());
//		buttonShowMarker.selectedProperty().addListener((observable, oldValue, newValue) ->{
//			if(newValue==null) return;
//			lineChart.setCreateSymbols(newValue);
//		});
		toggleLegend.selectedProperty().addListener((observable, oldValue, newValue) ->{
			if(newValue==null) return;
			lineChart.setLegendVisible(newValue);
		});


		toggleAutoRange.setSelected(true);
		
		textXlimLow.disableProperty().bind(toggleAutoRange.selectedProperty());
		textXlimHigh.disableProperty().bind(toggleAutoRange.selectedProperty());
		textYlimLow.disableProperty().bind(toggleAutoRange.selectedProperty());
		textYlimHigh.disableProperty().bind(toggleAutoRange.selectedProperty());
		
		xAxis.autoRangingProperty().bindBidirectional(toggleAutoRange.selectedProperty());
		yAxis.autoRangingProperty().bindBidirectional(toggleAutoRange.selectedProperty());
		
		StringConverter<Number> converter = new NumberStringConverter();
		Bindings.bindBidirectional(textXlimLow.textProperty(), xAxis.lowerBoundProperty(), converter);
		Bindings.bindBidirectional(textXlimHigh.textProperty(), xAxis.upperBoundProperty(), converter);
		Bindings.bindBidirectional(textYlimLow.textProperty(), yAxis.lowerBoundProperty(), converter);
		Bindings.bindBidirectional(textYlimHigh.textProperty(), yAxis.upperBoundProperty(), converter);
	    
		buttonShowMarker.setSelected(true);
		
//		buttonRefreshFolder.setOnAction((event) -> {
//			int tmpInt = listCalcFolders.getSelectionModel().getSelectedIndex();
//			updateProjectFolder();
//			if(tmpInt>=0 && listCalcFolders.getItems()!=null && listCalcFolders.getItems().size()>tmpInt) {
//				listCalcFolders.getSelectionModel().select(tmpInt);
//			}
//		});
		buttonRefreshFiles.setOnAction((event) -> {
			updateFilesInCalcFolder(false);
		});
//		deleteFolderButton.setOnAction((event) -> {
//			try {
//				deleteDirectory(calcFolder);
//			} catch (IOException e) {
//				e.printStackTrace();
//			}
//			updateProjectFolder();
//		});
		deleteFileButton.setOnAction((event) -> {
			try {
				deleteDirectory(inoutFiles);
			} catch (IOException e) {
				e.printStackTrace();
			}
			updateFilesInCalcFolder(true);
		});
		hboxPlotToolbar.setVisible(false);
		hboxBandsToolbar.setVisible(false);
		
		
		buttonSaveGeo.setDisable(true);
		buttonSaveGeo.setOnAction((event) -> {
			if(fileData==null) {return;}
//			ArrayList<Atom> atomList = fileData.getFinalAtomicPositions();
//			CellParameter cellPara = fileData.getFinalCellParameter();
//			Double alat = fileData.getAlat();
//			if(atomList==null || atomList.isEmpty() || alat==null ) {return;}
//			String calcFolderName = listCalcFolders.getSelectionModel().getSelectedItem();
			String calcFolderName = mainClass.projectManager.getCurrentCalcName();
			if(calcFolderName==null) {return;}
			//mainClass.projectManager.addGeoList(calcFolderName, atomList, cellPara, alat);
			mainClass.projectManager.addGeoList(calcFolderName, fileData.getGeoAgent());
			if(contGeo!=null) {contGeo.loadProjectParameters();}
		});
	}
	protected abstract void updateComboAnalysis();
	protected abstract void getFileCategory(String newTab);
	protected abstract boolean loadFile();
	protected abstract void updateIoDisplay();
	public void calculationFolderChange(String newCalcFolderName) {
		fileData.clearAll();buttonSaveGeo.setDisable(true);
		this.displayScroll.setContent(null);
		this.lineChart.getData().clear();
		this.xAxis.setLabel("");
		this.yAxis.setLabel("");
		
		if(newCalcFolderName==null || newCalcFolderName.isEmpty()) return;
		
		File pjFolder = getProjectFolder();
		if(pjFolder==null || !pjFolder.canRead()) {
			listFiles.getItems().clear();
			//return;//comment out so that calcFolder is always updated
		}
		if(pjFolder==null) {return;}
		calcFolder = new File(pjFolder,newCalcFolderName);
		
		updateFilesInCalcFolder(true);
	}
	protected void updateFilesInCalcFolder(boolean forceClean) {
		
		int tmpInt = listFiles.getSelectionModel().getSelectedIndex();
		
		if(forceClean) {
			listFiles.getItems().clear();
		}

		if(calcFolder==null || !calcFolder.canRead() || !calcFolder.isDirectory()) return;
		
		ObservableList<String> listFilesItems = FXCollections.observableArrayList();
		
		File[] fileList = calcFolder.listFiles();
		for (File f : fileList) {
			listFilesItems.add(f.getName());
		}
		
		if(this.checkIdentity(listFilesItems, listFiles.getItems())) {
			return;//no change, do nothing
		}
		
		listFiles.getItems().clear();
		listFiles.getItems().addAll(listFilesItems);
		
		String itemImportant = null;
		for(String item:listFilesItems) {
			if(isFileImportant(item)) {
				itemImportant = item;//only take the first important one
				break;
			}
		}
		if(itemImportant!=null) {
			listFiles.getSelectionModel().select(itemImportant);//automatically select the "important/highlighted" output file
			//will invoke selection change listener and update "inoutFiles"
		}
		else if(tmpInt>=0 && listFiles.getItems().size()>tmpInt) {//if no important file, just keep selected index
			listFiles.getSelectionModel().select(tmpInt);
		}
		else if(!listFiles.getItems().isEmpty()){//select first file if nothing works
			listFiles.getSelectionModel().select(0);
		}
	}
	protected File getProjectFolder() {
		String wsp = mainClass.projectManager.workSpacePath;
		String pj = mainClass.projectManager.getActiveProjectName();
		if(wsp==null || pj==null || pj.isEmpty()) return null;
		return new File(new File(wsp),pj);
	}
	protected boolean checkIdentity(ObservableList<String> lst1, ObservableList<String> lst2) {
		if(lst1==null && lst2==null) {return true;}//both null
		else if(lst1==null || lst2==null) {return false;}//only one is null
		else {//both not null
			if(lst1.size()!=lst2.size()) {return false;}
			else {
				for(int i=0;i<lst1.size();i++) {
					if(!Objects.equals(lst1.get(i),lst2.get(i))) {return false;}
				}
				return true;
			}
		}
	}
	protected abstract boolean isFileImportant(String item);
	protected void plotOptArray(ArrayList<ArrayList<Double>> dataY, String xlabel, String ylabel, String titleStr) {
		xAxis.setLabel(xlabel);
		yAxis.setLabel(ylabel);
		if(dataY!=null && !dataY.isEmpty()) {
			Series<Double,Double> dataSeries1 = new Series<Double, Double>();
	        dataSeries1.setName(titleStr);
			
			for(int i=0;i<dataY.size();i++) {
				if(dataY.get(i).size()>0) {
					Double dbTmp = dataY.get(i).get(dataY.get(i).size()-1);
					if(dbTmp!=null) {dataSeries1.getData().add(new Data<Double, Double>( (double) i+1, dbTmp));}
				}
			}
			lineChart.getData().add(dataSeries1);
		}
	}
	protected void plotScfArray(ArrayList<ArrayList<Double>> dataY, String xlabel, String ylabel, String titleStr) {
		xAxis.setLabel(xlabel);
		yAxis.setLabel(ylabel);
        if(dataY!=null && !dataY.isEmpty()) {
        	Series<Double,Double> dataSeries1 = new Series<Double, Double>();
            dataSeries1.setName(titleStr);
			ArrayList<Double> scfTmp = dataY.get(dataY.size()-1);
			if(scfTmp.isEmpty() && dataY.size()>=2) {scfTmp = dataY.get(dataY.size()-2);}
			Data<Double, Double> dataTmp;
			for(int i=0;i<scfTmp.size();i++) {
				dataTmp = new Data<Double, Double>( (double) i+1, scfTmp.get(i));
				//ShowAlert.showAlert("Debug", dataTmp.getNode().toString());
		        dataSeries1.getData().add(dataTmp);
			}
			lineChart.getData().add(dataSeries1);
			
        }
	}
	protected void plotArray(ArrayList<Double> dataY, String xlabel, String ylabel, String titleStr, boolean boolClear) {
		if(boolClear) {lineChart.getData().clear();}
		if(dataY==null) {return;}
		xAxis.setLabel(xlabel);
		yAxis.setLabel(ylabel);
		Series<Double,Double> dataSeries1 = new Series<Double, Double>();
        dataSeries1.setName(titleStr);
		
		for(int i=0;i<dataY.size();i++) {
			if(dataY.get(i)==null) {continue;}
			dataSeries1.getData().add(new Data<Double, Double>( (double) i+1, dataY.get(i)));
		}
		lineChart.getData().add(dataSeries1);
	}
	protected boolean isSameTypeStdout(ArrayList<String> strTest) {
		ObservableList<String> comboTmp = comboPlot.getItems();
		if(comboTmp.size()!=strTest.size()) {return false;}
		for(int i=0;i<comboTmp.size();i++) {
			if(comboTmp.get(i)==null || !comboTmp.get(i).equals(strTest.get(i))) {return false;}
		}
		return true;
	}
	protected boolean deleteDirectory(File directoryToBeDeleted) throws IOException {
	    File[] contentFiles = directoryToBeDeleted.listFiles();
	    if (contentFiles != null) {
	        for (File file : contentFiles) {
	            deleteDirectory(file);
	        }
	    }
	    return directoryToBeDeleted.delete();
	}
}
